"""
Two-Phase Commit (2PC) implementation với Recovery
"""

import uuid
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple

import pymysql

from config import (
    PREPARE_TIMEOUT,
    DB1_CONFIG,
    DB2_CONFIG,
    ALL_DB_CONFIGS,
    PHASE_LABELS
)
from database import get_connection, get_log_conn
from logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Phase Logging
# =============================================================================

def log_phase(
    tx_id: str,
    xid: str,
    phase: str,
    from_acc: Dict[str, Any] = None,
    to_acc: Dict[str, Any] = None,
    amount: float = None,
    description: str = ''
):
    """
    Ghi / cập nhật trạng thái phase vào transaction_log VÀ file .log

    Args:
        tx_id: Transaction ID hiển thị
        xid: XA Transaction ID
        phase: Tên phase
        from_acc: Thông tin tài khoản nguồn
        to_acc: Thông tin tài khoản đích
        amount: Số tiền
        description: Mô tả giao dịch
    """
    label = PHASE_LABELS.get(phase, phase)

    # Ghi file log
    if phase == 'PREPARING':
        logger.info(
            '[PHASE] %s | tx=%s | %s | %s → %s | %.0fđ | "%s"',
            label, tx_id, xid[:12],
            from_acc['account_number'], to_acc['account_number'],
            amount, description
        )
    elif phase in ('COMMITTED', 'COMPENSATED'):
        logger.info('[PHASE] %s | tx=%s', label, tx_id)
    elif phase in ('ABORTED', 'TIMEOUT', 'COMMIT_A'):
        logger.warning('[PHASE] %s | tx=%s', label, tx_id)
    elif phase == 'COMPENSATING':
        logger.warning('[PHASE] %s | tx=%s', label, tx_id)
    else:
        logger.info('[PHASE] %s | tx=%s', label, tx_id)

    # Ghi DB
    try:
        conn = get_log_conn()
        with conn.cursor() as cur:
            if phase == 'PREPARING':
                cur.execute(
                    "INSERT INTO transaction_log "
                    "(tx_id, xid, from_account_number, from_name, to_account_number, to_name, amount, description, phase) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'PREPARING')",
                    (tx_id, xid,
                     from_acc['account_number'], from_acc['name'],
                     to_acc['account_number'], to_acc['name'],
                     amount, description)
                )
            else:
                cur.execute(
                    "UPDATE transaction_log SET phase=%s WHERE tx_id=%s",
                    (phase, tx_id)
                )
        conn.close()
    except Exception as e:
        logger.error('[PHASE] Lỗi ghi transaction_log (%s): %s', phase, e)


# =============================================================================
# XA Transaction Helpers
# =============================================================================

def xa_rollback(config: Dict[str, Any], xid: str):
    """
    Rollback XA transaction trên một database

    Args:
        config: Database configuration
        xid: XA Transaction ID
    """
    try:
        conn = get_connection({**config, 'autocommit': True})
        with conn.cursor() as c:
            c.execute(f"XA ROLLBACK '{xid}'")
        conn.close()
    except Exception as e:
        logger.warning('[XA] Lỗi XA ROLLBACK (%s): %s', config['database'], e)


def xa_commit(config: Dict[str, Any], xid: str) -> bool:
    """
    Commit XA transaction trên một database

    Args:
        config: Database configuration
        xid: XA Transaction ID

    Returns:
        True nếu commit thành công
    """
    try:
        conn = get_connection({**config, 'autocommit': True})
        with conn.cursor() as c:
            c.execute(f"XA COMMIT '{xid}'")
        conn.close()
        return True
    except Exception as e:
        logger.error('[XA] Lỗi XA COMMIT (%s): %s', config['database'], e)
        return False


def rollback_xa_all(xid: str, configs: List[Dict[str, Any]]):
    """
    Rollback XA trên tất cả database configs

    Args:
        xid: XA Transaction ID
        configs: List các database configs
    """
    for cfg in configs:
        xa_rollback(cfg, xid)


# =============================================================================
# Compensating Transaction — Kịch bản 4
# =============================================================================

def do_compensation(
    tx_id: str,
    xid: str,
    from_account_number: str,
    amount: float,
    from_acc: Dict[str, Any] = None,
    from_config: Dict[str, Any] = None
) -> bool:
    """
    Bank A đã COMMIT (tiền đã trừ) nhưng Bank B chưa COMMIT.
    Tạo giao dịch bù: cộng lại số tiền cho tài khoản nguồn (Bank A).

    Args:
        tx_id: Transaction ID
        xid: XA Transaction ID
        from_account_number: Số tài khoản nguồn
        amount: Số tiền cần hoàn
        from_acc: Thông tin tài khoản (nếu đã có)
        from_config: Database config (nếu đã có)

    Returns:
        True nếu compensation thành công
    """
    from account_service import find_account_by_number

    logger.warning('[COMPENSATE] Bắt đầu hoàn tiền | tx=%s | acc=%s | amount=%.0f',
                   tx_id, from_account_number, amount)

    # Lấy thông tin tài khoản nếu chưa có
    if from_acc is None or from_config is None:
        from_acc, from_config = find_account_by_number(from_account_number)

    if not from_acc:
        logger.error('[COMPENSATE] Không tìm thấy tài khoản nguồn %s', from_account_number)
        return False

    try:
        log_phase(tx_id, xid, 'COMPENSATING')
        conn = get_connection({**from_config, 'autocommit': True})
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                (amount, from_acc['id'])
            )
        conn.close()
        log_phase(tx_id, xid, 'COMPENSATED')
        logger.info('[COMPENSATE] Hoàn %.0fđ → %s thành công | tx=%s',
                    amount, from_account_number, tx_id)

        # Ghi transaction compensation
        comp_tx_id = 'COMP-' + tx_id
        try:
            lc = get_log_conn()
            with lc.cursor() as cur:
                cur.execute(
                    "INSERT INTO transactions "
                    "(tx_id, from_account_number, from_name, to_account_number, to_name, amount, description, status) "
                    "VALUES (%s,'SYSTEM','Hệ thống',%s,%s,%s,%s,'COMPENSATED')",
                    (comp_tx_id,
                     from_acc['account_number'], from_acc['name'],
                     amount, f'Hoàn tiền bù giao dịch lỗi {tx_id}')
                )
            lc.close()
        except Exception as log_err:
            logger.error('[COMPENSATE] Lỗi ghi transactions: %s', log_err)

        return True

    except Exception as e:
        logger.error('[COMPENSATE] Lỗi thực hiện compensation %s: %s', tx_id, e)
        return False


# =============================================================================
# XA Prepare Worker (chạy trong thread riêng)
# =============================================================================

def xa_prepare_participant(config: Dict[str, Any], xid: str, account_id: int, amount: float, is_debit: bool):
    """
    Worker chạy trong thread riêng (Phase 1).
    Thực hiện: XA START → UPDATE balance → XA END → XA PREPARE.

    Args:
        config: Database configuration
        xid: XA Transaction ID
        account_id: Account ID
        amount: Số tiền
        is_debit: True nếu trừ tiền (debit), False nếu cộng tiền (credit)
    """
    conn = get_connection(config)
    try:
        cur = conn.cursor()
        cur.execute(f"XA START '{xid}'")
        if is_debit:
            cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s",
                        (amount, account_id))
        else:
            cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s",
                        (amount, account_id))
        cur.execute(f"XA END '{xid}'")
        cur.execute(f"XA PREPARE '{xid}'")
    finally:
        conn.close()  # XA PREPARED — state được giữ bởi MySQL


# =============================================================================
# Recovery: xử lý giao dịch treo khi TC khởi động lại
# =============================================================================

def recover_in_doubt_transactions() -> List[Dict[str, Any]]:
    """
    Quét XA transactions đang PREPARED và log entries chưa hoàn tất.
    Xử lý từng kịch bản:
      PREPARING          → XA ROLLBACK (sập trước khi PREPARE hoàn tất)
      PREPARED/COMMITTING → XA COMMIT tất cả participant còn PREPARED
      COMMIT_A           → XA COMMIT Bank B nếu còn PREPARED; nếu không → Compensation
      COMPENSATING       → Chạy lại compensation bị gián đoạn

    Returns:
        List of recovered transactions
    """
    logger.info('[RECOVERY] ════════ Bắt đầu kiểm tra giao dịch treo ════════')
    recovered = []

    # Bước 1: XA RECOVER — map xid → list configs còn PREPARED
    in_doubt = {}
    for config in ALL_DB_CONFIGS:
        try:
            conn = get_connection({**config, 'autocommit': True})
            with conn.cursor() as cur:
                cur.execute("XA RECOVER")
                for row in cur.fetchall():
                    xid = row[3]
                    in_doubt.setdefault(xid, []).append(config)
            conn.close()
        except Exception as e:
            logger.error('[RECOVERY] Lỗi XA RECOVER: %s', e)

    # Bước 2: đọc tất cả log entry chưa kết thúc
    try:
        lc = get_log_conn()
        with lc.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM transaction_log "
                "WHERE phase IN ('PREPARING','PREPARED','COMMITTING','COMMIT_A','COMPENSATING')"
            )
            pending_logs = {row['xid']: row for row in cur.fetchall()}
        lc.close()
    except Exception as e:
        logger.error('[RECOVERY] Lỗi đọc transaction_log: %s', e)
        pending_logs = {}

    all_xids = set(in_doubt.keys()) | set(pending_logs.keys())

    if not all_xids:
        logger.info('[RECOVERY] Không có giao dịch treo.')
        return []

    logger.info('[RECOVERY] Tìm thấy %d giao dịch cần xử lý.', len(all_xids))

    for xid in all_xids:
        log_entry = pending_logs.get(xid)
        phase = log_entry['phase'] if log_entry else None
        tx_id = log_entry['tx_id'] if log_entry else xid
        prepared_on = in_doubt.get(xid, [])  # configs còn PREPARED

        logger.info('[RECOVERY] tx=%s | phase=%s | PREPARED trên %d DB', tx_id, phase, len(prepared_on))

        # ── Kịch bản 4: Bank A đã COMMIT, Bank B chưa COMMIT ─────────────
        if phase == 'COMMIT_A':
            if prepared_on:
                # Bank B vẫn trong XA PREPARED → có thể hoàn tất COMMIT
                commit_ok = xa_commit(prepared_on[0], xid) if prepared_on else False

                if commit_ok:
                    log_phase(tx_id, xid, 'COMMITTED')
                    recovered.append({'tx_id': tx_id, 'xid': xid, 'action': 'COMMIT_B_COMPLETED'})
                else:
                    # Không COMMIT được → XA ROLLBACK Bank B + Compensation Bank A
                    rollback_xa_all(xid, prepared_on)
                    ok = do_compensation(
                        tx_id, xid,
                        log_entry['from_account_number'],
                        float(log_entry['amount'])
                    )
                    recovered.append({
                        'tx_id': tx_id, 'xid': xid,
                        'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'
                    })
            else:
                # Bank B không còn trong XA RECOVER → bắt buộc Compensation
                logger.warning('[RECOVERY] tx=%s: Bank B mất XA state → thực hiện compensation', tx_id)
                ok = do_compensation(
                    tx_id, xid,
                    log_entry['from_account_number'],
                    float(log_entry['amount'])
                )
                recovered.append({
                    'tx_id': tx_id, 'xid': xid,
                    'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'
                })

        # ── Compensation bị gián đoạn → chạy lại ────────────────────────
        elif phase == 'COMPENSATING' and log_entry:
            ok = do_compensation(
                tx_id, xid,
                log_entry['from_account_number'],
                float(log_entry['amount'])
            )
            recovered.append({
                'tx_id': tx_id, 'xid': xid,
                'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'
            })

        # ── PREPARED / COMMITTING: sập sau Phase 1 → tiếp tục COMMIT ────
        elif phase in ('PREPARED', 'COMMITTING'):
            for config in prepared_on:
                xa_commit(config, xid)
            log_phase(tx_id, xid, 'COMMITTED')
            recovered.append({'tx_id': tx_id, 'xid': xid, 'action': 'COMMITTED'})

        # ── PREPARING hoặc không rõ: rollback ────────────────────────────
        else:
            rollback_xa_all(xid, prepared_on)
            if log_entry:
                log_phase(tx_id, xid, 'ABORTED')
            recovered.append({'tx_id': tx_id, 'xid': xid, 'action': 'ABORTED'})

    return recovered


# =============================================================================
# Main 2PC Transfer Execution
# =============================================================================

def execute_transfer(
    from_acc: Dict[str, Any],
    from_config: Dict[str, Any],
    to_acc: Dict[str, Any],
    to_config: Dict[str, Any],
    amount: float,
    description: str
) -> Tuple[bool, str, str, Optional[Dict[str, Any]]]:
    """
    Thực hiện giao dịch 2-Phase Commit

    Args:
        from_acc: Thông tin tài khoản nguồn
        from_config: Database config của tài khoản nguồn
        to_acc: Thông tin tài khoản đích
        to_config: Database config của tài khoản đích
        amount: Số tiền
        description: Mô tả giao dịch

    Returns:
        Tuple: (success, message, tx_id, extra_data)
    """
    from account_service import save_transaction

    xid = str(uuid.uuid4()).replace("-", "")
    tx_id = 'VB' + xid[:10].upper()
    commit_a_done = False

    logger.info('[TRANSFER] ── Giao dịch mới | tx=%s | %s → %s | %.0fđ | "%s"',
                tx_id, from_acc['account_number'], to_acc['account_number'], amount, description)
    log_phase(tx_id, xid, 'PREPARING', from_acc, to_acc, amount, description)

    # ===== PHASE 1: XA PREPARE — chạy song song, có timeout =====
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_from = executor.submit(
            xa_prepare_participant, from_config, xid, from_acc['id'], amount, True)
        future_to = executor.submit(
            xa_prepare_participant, to_config, xid, to_acc['id'], amount, False)

        done, pending = concurrent.futures.wait(
            [future_from, future_to], timeout=PREPARE_TIMEOUT)

    # ── Kiểm tra timeout ───────────────────────────────────────────────
    if pending:
        slow = []
        if future_from in pending:
            slow.append('Bank A (nguồn)')
        if future_to in pending:
            slow.append('Bank B (đích)')
        slow_str = ', '.join(slow)
        logger.warning('[TIMEOUT] tx=%s | %s không phản hồi PREPARE sau %ds',
                      tx_id, slow_str, PREPARE_TIMEOUT)
        log_phase(tx_id, xid, 'TIMEOUT')
        rollback_xa_all(xid, [from_config, to_config])
        return (
            False,
            f"Kịch bản 5 — Timeout: {slow_str} không phản hồi "
            f"trong {PREPARE_TIMEOUT}s. Đã tự động hủy giao dịch, "
            f"không tài khoản nào thay đổi số dư.",
            tx_id,
            {'timeout': True}
        )

    # ── Kiểm tra lỗi từ các future ─────────────────────────────────────
    for future in [future_from, future_to]:
        exc = future.exception()
        if exc is not None:
            logger.error('[TRANSFER] tx=%s: Phase 1 thất bại | lỗi=%s', tx_id, exc)
            log_phase(tx_id, xid, 'ABORTED')
            rollback_xa_all(xid, [from_config, to_config])
            return (
                False,
                f"Giao dịch thất bại ở Phase 1: {str(exc)}",
                tx_id,
                None
            )

    # ── Cả hai đã PREPARE thành công ───────────────────────────────────
    log_phase(tx_id, xid, 'PREPARED')

    # ===== PHASE 2: COMMIT =====
    try:
        log_phase(tx_id, xid, 'COMMITTING')

        # Bank A (nguồn) commit trước
        ca = get_connection({**from_config, 'autocommit': True})
        with ca.cursor() as c:
            c.execute(f"XA COMMIT '{xid}'")
        ca.close()

        log_phase(tx_id, xid, 'COMMIT_A')
        commit_a_done = True

        # Bank B (đích) commit
        cb = get_connection({**to_config, 'autocommit': True})
        with cb.cursor() as c:
            c.execute(f"XA COMMIT '{xid}'")
        cb.close()

        log_phase(tx_id, xid, 'COMMITTED')

        # Lưu hóa đơn
        save_transaction(
            tx_id=tx_id,
            from_acc=from_acc,
            to_acc=to_acc,
            amount=amount,
            description=description,
            status='SUCCESS'
        )

        logger.info('[TRANSFER] ✓ Hoàn tất | tx=%s | %.0fđ | %s → %s',
                    tx_id, amount, from_acc['account_number'], to_acc['account_number'])

        return (
            True,
            "Chuyển tiền thành công! (2-Phase Commit Hoàn tất)",
            tx_id,
            None
        )

    except Exception as e:
        if commit_a_done:
            # Kịch bản 4: Bank A đã COMMIT, Bank B chưa
            logger.error('[PARTIAL COMMIT] tx=%s: Bank A committed, Bank B failed → compensation', tx_id)

            # Rollback Bank B
            xa_rollback(to_config, xid)

            # Compensation cho Bank A
            ok = do_compensation(tx_id, xid, from_acc['account_number'], amount, from_acc, from_config)

            return (
                False,
                "Lỗi COMMIT lệch pha (Kịch bản 4): "
                "Bank A đã trừ tiền nhưng Bank B chưa nhận. "
                + ("Đã hoàn tiền tự động cho người gửi." if ok
                   else "CẢNH BÁO: Hoàn tiền thất bại — cần xử lý thủ công!"),
                tx_id,
                {'partial_failure': True, 'compensation': ok}
            )
        else:
            logger.error('[TRANSFER] tx=%s: Phase 2 thất bại | lỗi=%s', tx_id, e)
            log_phase(tx_id, xid, 'ABORTED')
            rollback_xa_all(xid, [from_config, to_config])
            return (
                False,
                f"Giao dịch thất bại, đã Rollback: {str(e)}",
                tx_id,
                None
            )