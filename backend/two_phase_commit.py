"""
Two-Phase Commit (2PC) implementation với Recovery
"""

import concurrent.futures
import logging
import os
import uuid
from typing import Dict, Any, List, Optional, Tuple

import pymysql

from config import (
    PREPARE_TIMEOUT,
    ALL_DB_CONFIGS,
    PHASE_LABELS
)
from database import get_connection, get_coordinator_conn
from logger import get_logger

logger = get_logger(__name__)
TC04_COMMIT_B_FAIL_TOKEN = 'TC04_B_COMMIT_FAIL'
TC05_CRASH_AFTER_COMMIT_A_TOKEN = 'TC05_CRASH_AFTER_COMMIT_A'
TC06_CRASH_BEFORE_COMMIT_TOKEN = 'TC06_CRASH_BEFORE_COMMIT'
TC07_CRASH_AFTER_PREPARE_TOKEN = 'TC07_CRASH_AFTER_PREPARE'
TC08_CRASH_DURING_COMMITTING_TOKEN = 'TC08_CRASH_DURING_COMMITTING'
TC09_COMMIT_TWICE_TOKEN = 'TC09_COMMIT_TWICE'
TC10_ROLLBACK_TWICE_TOKEN = 'TC10_ROLLBACK_TWICE'
_TX_LOG_SCHEMA_CACHE: Dict[str, Dict[str, Dict[str, Any]]] = {}


def has_demo_token(description: str, token: str) -> bool:
    return token in (description or '').upper()


def should_simulate_commit_b_failure(description: str) -> bool:
    """Demo hook: force Bank B commit failure from the UI transfer note."""
    return has_demo_token(description, TC04_COMMIT_B_FAIL_TOKEN)


def should_simulate_coordinator_crash_after_commit_a(description: str) -> bool:
    """Demo hook: crash the coordinator after Bank A commits."""
    return has_demo_token(description, TC05_CRASH_AFTER_COMMIT_A_TOKEN)


def crash_coordinator_for_demo(tx_id: str, reason: str):
    logger.critical('[DEMO] tx=%s: %s', tx_id, reason)
    logging.shutdown()
    os._exit(1)


def _phase_to_business_status(phase: str) -> str:
    if phase in ('COMMITTED', 'COMPENSATED'):
        return 'SUCCESS'
    if phase in ('ABORTED', 'TIMEOUT'):
        return 'FAILED'
    if phase == 'COMPENSATING':
        return 'COMPENSATING'
    return 'PROCESSING'


def _get_transaction_log_schema(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Đọc schema transaction_log thực tế từ từng bank để tương thích schema cũ/mới.
    """
    db_name = str(config.get('database') or '')
    cached = _TX_LOG_SCHEMA_CACHE.get(db_name)
    if cached is not None:
        return cached

    schema: Dict[str, Dict[str, Any]] = {}
    conn = None
    try:
        conn = get_connection({**config, 'autocommit': True})
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA "
                "FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = 'transaction_log' "
                "ORDER BY ORDINAL_POSITION",
                (db_name,),
            )
            for row in cur.fetchall():
                col = str(row.get('COLUMN_NAME') or '')
                if not col:
                    continue
                schema[col] = {
                    'data_type': str(row.get('DATA_TYPE') or '').lower(),
                    'is_nullable': str(row.get('IS_NULLABLE') or '').upper() == 'YES',
                    'default': row.get('COLUMN_DEFAULT'),
                    'extra': str(row.get('EXTRA') or '').lower(),
                }
    except Exception as e:
        logger.warning(
            '[PHASE] Khong the doc schema transaction_log tu %s: %s',
            config.get('database'),
            e,
        )
    finally:
        if conn:
            conn.close()

    if not schema:
        schema = {
            'tx_id': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'xid': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'phase': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'amount': {'data_type': 'decimal', 'is_nullable': True, 'default': None, 'extra': ''},
        }

    _TX_LOG_SCHEMA_CACHE[db_name] = schema
    return schema


def _required_fallback_value(
    column_name: str,
    column_meta: Dict[str, Any],
    tx_id: str,
    xid: str,
    phase: str,
    from_acc: Optional[Dict[str, Any]],
    to_acc: Optional[Dict[str, Any]],
    amount: Optional[float],
    description: str,
):
    from_acc = from_acc or {}
    to_acc = to_acc or {}

    mapping = {
        'tx_id': tx_id,
        'xid': xid or '',
        'phase': phase,
        'amount': amount if amount is not None else 0,
        'from_account_number': from_acc.get('account_number') or '',
        'to_account_number': to_acc.get('account_number') or '',
        'from_account': from_acc.get('account_number') or '',
        'to_account': to_acc.get('account_number') or '',
        'from_name': from_acc.get('name') or '',
        'to_name': to_acc.get('name') or '',
        'description': description or '',
        'status': _phase_to_business_status(phase),
    }
    if column_name in mapping:
        return mapping[column_name]

    data_type = str(column_meta.get('data_type') or '')
    if data_type in ('tinyint', 'smallint', 'mediumint', 'int', 'bigint', 'decimal', 'float', 'double'):
        return 0
    return ''


def _build_participant_log_upsert(
    tx_id: str,
    xid: str,
    phase: str,
    from_acc: Optional[Dict[str, Any]],
    to_acc: Optional[Dict[str, Any]],
    amount: Optional[float],
    description: str,
    table_schema: Dict[str, Dict[str, Any]],
) -> Tuple[str, Tuple[Any, ...]]:
    candidates = {
        'tx_id': tx_id,
        'xid': xid,
        'phase': phase,
        'amount': amount,
        'from_account_number': (from_acc or {}).get('account_number'),
        'to_account_number': (to_acc or {}).get('account_number'),
        'from_account': (from_acc or {}).get('account_number'),
        'to_account': (to_acc or {}).get('account_number'),
        'from_name': (from_acc or {}).get('name'),
        'to_name': (to_acc or {}).get('name'),
        'description': description or '',
        'status': _phase_to_business_status(phase),
    }

    columns: List[str] = []
    values: List[Any] = []

    for col, meta in table_schema.items():
        if 'auto_increment' in str(meta.get('extra') or ''):
            continue
        if col == 'created_at':
            continue

        value = candidates.get(col)
        if value is None:
            default_value = meta.get('default')
            if default_value is not None:
                continue
            if meta.get('is_nullable'):
                value = None
            else:
                value = _required_fallback_value(
                    col, meta, tx_id, xid, phase, from_acc, to_acc, amount, description
                )

        columns.append(col)
        values.append(value)

    if 'tx_id' not in columns:
        columns.insert(0, 'tx_id')
        values.insert(0, tx_id)

    update_columns = [c for c in columns if c not in ('tx_id', 'id', 'created_at')]
    if update_columns:
        update_sql = ', '.join(f"`{c}` = VALUES(`{c}`)" for c in update_columns)
    else:
        update_sql = "`tx_id` = `tx_id`"

    column_sql = ', '.join(f"`{c}`" for c in columns)
    placeholder_sql = ', '.join(['%s'] * len(columns))
    sql = (
        f"INSERT INTO transaction_log ({column_sql}) "
        f"VALUES ({placeholder_sql}) "
        f"ON DUPLICATE KEY UPDATE {update_sql}"
    )
    return sql, tuple(values)


def _build_participant_recovery_select(table_schema: Dict[str, Dict[str, Any]]) -> str:
    from_col = None
    if 'from_account' in table_schema:
        from_col = 'from_account'
    elif 'from_account_number' in table_schema:
        from_col = 'from_account_number'

    to_col = None
    if 'to_account' in table_schema:
        to_col = 'to_account'
    elif 'to_account_number' in table_schema:
        to_col = 'to_account_number'

    select_parts = ['tx_id', 'xid', 'phase', 'amount']
    if from_col:
        select_parts.append(f"{from_col} AS from_account")
    else:
        select_parts.append("NULL AS from_account")
    if to_col:
        select_parts.append(f"{to_col} AS to_account")
    else:
        select_parts.append("NULL AS to_account")

    select_sql = ', '.join(select_parts)
    return (
        f"SELECT {select_sql} FROM transaction_log "
        "WHERE phase IN ('PREPARING','PREPARED','COMMITTING','COMMIT_A','COMPENSATING')"
    )


def _pick_recovery_accounts(
    tx_meta: Dict[str, Any],
    log_entry: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str]]:
    from_account = (
        (tx_meta or {}).get('from_account')
        or (log_entry or {}).get('from_account')
    )
    to_account = (
        (tx_meta or {}).get('to_account')
        or (log_entry or {}).get('to_account')
    )
    return from_account, to_account


def _is_terminal_phase_or_status(value: Optional[str]) -> bool:
    return str(value or '').upper() in {
        'COMMITTED',
        'ABORTED',
        'COMPENSATED',
        'SUCCESS',
        'FAILED',
    }


# =============================================================================
# Phase Logging
# =============================================================================

def log_phase(
    tx_id: str,
    xid: str,
    phase: str,
    from_acc: Dict[str, Any] = None,
    to_acc: Dict[str, Any] = None,
    from_config: Dict[str, Any] = None,
    to_config: Dict[str, Any] = None,
    amount: float = None,
    description: str = ''
):
    """
    Ghi / cập nhật trạng thái phase vào transaction_log và output log trên console

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

    # Ghi coordinator DB
    try:
        conn = get_coordinator_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO transactions (tx_id, from_account, to_account, amount, status) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "from_account = COALESCE(VALUES(from_account), from_account), "
                "to_account = COALESCE(VALUES(to_account), to_account), "
                "amount = COALESCE(VALUES(amount), amount), "
                "status = VALUES(status)",
                (
                    tx_id,
                    from_acc['account_number'] if from_acc else None,
                    to_acc['account_number'] if to_acc else None,
                    amount,
                    phase,
                )
            )
        conn.close()
    except Exception as e:
        logger.error('[PHASE] Lỗi ghi coordinator transactions (%s): %s', phase, e)

    # Ghi participant log trên từng bank liên quan
    participant_targets = []
    if from_config is not None:
        participant_targets.append(from_config)
    if to_config is not None and to_config is not from_config:
        participant_targets.append(to_config)

    for config in participant_targets:
        bank_conn = None
        try:
            tx_log_schema = _get_transaction_log_schema(config)
            participant_sql, participant_params = _build_participant_log_upsert(
                tx_id=tx_id,
                xid=xid,
                phase=phase,
                from_acc=from_acc,
                to_acc=to_acc,
                amount=amount,
                description=description,
                table_schema=tx_log_schema,
            )
            bank_conn = get_connection({**config, 'autocommit': True})
            with bank_conn.cursor() as cur:
                cur.execute(participant_sql, participant_params)
        except Exception as e:
            logger.error(
                '[PHASE] Lỗi ghi participant transaction_log (%s/%s): %s',
                config.get('database'),
                phase,
                e,
            )
        finally:
            if bank_conn:
                bank_conn.close()


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


def _is_xa_unknown_xid_error(err: Exception) -> bool:
    code = None
    if getattr(err, 'args', None):
        code = err.args[0]
    msg = str(err)
    return code == 1397 or 'XAER_NOTA' in msg or 'Unknown XID' in msg


def xa_commit(config: Dict[str, Any], xid: str, tolerate_unknown_xid: bool = False) -> bool:
    """
    Commit XA transaction trên một database

    Args:
        config: Database configuration
        xid: XA Transaction ID
        tolerate_unknown_xid: Cho phép coi XAER_NOTA là hợp lệ (idempotent repeat)

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
        if tolerate_unknown_xid and _is_xa_unknown_xid_error(e):
            logger.info(
                '[XA] COMMIT lặp lại trên %s bỏ qua XAER_NOTA cho xid=%s',
                config['database'],
                xid,
            )
            return True
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


def log_balance(config: Dict[str, Any], account_number: str, tx_id: str, label: str):
    """Đọc số dư committed và ghi vào log (cả console lẫn .log file)."""
    try:
        conn = get_connection({**config, 'autocommit': True})
        with conn.cursor() as cur:
            cur.execute(
                "SELECT balance FROM accounts WHERE account_number = %s",
                (account_number,)
            )
            row = cur.fetchone()
        conn.close()
        if row is not None:
            logger.info(
                '[BAL] %-22s | tx=%-14s | acc=%s | balance=%.0f đ',
                label, tx_id, account_number, row[0]
            )
        else:
            logger.warning(
                '[BAL] %-22s | tx=%-14s | acc=%s | không tìm thấy',
                label, tx_id, account_number
            )
    except Exception as e:
        logger.error(
            '[BAL] %-22s | tx=%-14s | acc=%s | lỗi: %s',
            label, tx_id, account_number, e
        )


def _log_recovery_balances(tx_id: str, from_account: Optional[str], to_account: Optional[str], label: str) -> None:
    from account_service import find_account_by_number

    if from_account:
        from_acc, from_cfg = find_account_by_number(from_account)
        if from_acc and from_cfg:
            log_balance(from_cfg, from_acc['account_number'], tx_id, f'{label}-A')

    if to_account and to_account != from_account:
        to_acc, to_cfg = find_account_by_number(to_account)
        if to_acc and to_cfg:
            log_balance(to_cfg, to_acc['account_number'], tx_id, f'{label}-B')


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

    from_account_number = str(from_account_number or '').strip()
    logger.warning('[COMPENSATE] Bắt đầu hoàn tiền | tx=%s | acc=%s | amount=%.0f',
                   tx_id, from_account_number, amount)

    if not from_account_number and not from_acc:
        logger.error(
            '[COMPENSATE] tx=%s thiếu from_account_number, không thể tự động compensation',
            tx_id,
        )
        return False

    # Lấy thông tin tài khoản nếu chưa có
    if from_acc is None or from_config is None:
        lookup_key = from_account_number or (from_acc or {}).get('account_number')
        from_acc, from_config = find_account_by_number(lookup_key)

    if not from_acc:
        logger.error('[COMPENSATE] Không tìm thấy tài khoản nguồn %s', from_account_number)
        return False

    try:
        log_balance(from_config, from_acc['account_number'], tx_id, 'TRƯỚC-COMPENSATION')
        log_phase(tx_id, xid, 'COMPENSATING', from_acc, None, from_config, None, amount)
        conn = get_connection({**from_config, 'autocommit': True})
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance + %s WHERE account_number = %s",
                (amount, from_acc['account_number'])
            )
        conn.close()
        log_balance(from_config, from_acc['account_number'], tx_id, 'SAU-COMPENSATION(+hoàn)')
        log_phase(tx_id, xid, 'COMPENSATED', from_acc, None, from_config, None, amount)
        logger.info('[COMPENSATE] Hoàn %.0fđ → %s thành công | tx=%s',
                    amount, from_account_number, tx_id)

        return True

    except Exception as e:
        logger.error('[COMPENSATE] Lỗi thực hiện compensation %s: %s', tx_id, e)
        return False


# =============================================================================
# XA Prepare Worker (chạy trong thread riêng)
# =============================================================================

def xa_prepare_participant(
    config: Dict[str, Any],
    xid: str,
    account_number: str,
    amount: float,
    is_debit: bool
):
    """
    Worker chạy trong thread riêng (Phase 1).
    Thực hiện: XA START → UPDATE balance → XA END → XA PREPARE.

    Args:
        config: Database configuration
        xid: XA Transaction ID
        account_number: Account number
        amount: Số tiền
        is_debit: True nếu trừ tiền (debit), False nếu cộng tiền (credit)
    """
    conn = get_connection(config)
    try:
        cur = conn.cursor()
        cur.execute(f"XA START '{xid}'")
        if is_debit:
            cur.execute(
                "UPDATE accounts SET balance = balance - %s WHERE account_number = %s",
                (amount, account_number)
            )
        else:
            cur.execute(
                "UPDATE accounts SET balance = balance + %s WHERE account_number = %s",
                (amount, account_number)
            )
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

    # Bước 2: đọc tất cả log entry participant chưa kết thúc
    pending_logs = {}
    tx_to_accounts = {}
    for config in ALL_DB_CONFIGS:
        bank_conn = None
        try:
            tx_log_schema = _get_transaction_log_schema(config)
            recovery_sql = _build_participant_recovery_select(tx_log_schema)
            bank_conn = get_connection({**config, 'autocommit': True})
            with bank_conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(recovery_sql)
                for row in cur.fetchall():
                    entry = pending_logs.setdefault(
                        row['tx_id'],
                        {
                            'tx_id': row['tx_id'],
                            'xid': row['xid'],
                            'phase': row['phase'],
                            'amount': row['amount'],
                            'from_account': row.get('from_account'),
                            'to_account': row.get('to_account'),
                        }
                    )
                    if not entry.get('from_account') and row.get('from_account'):
                        entry['from_account'] = row.get('from_account')
                    if not entry.get('to_account') and row.get('to_account'):
                        entry['to_account'] = row.get('to_account')
        except Exception as e:
            logger.error('[RECOVERY] Lỗi đọc transaction_log từ %s: %s', config['database'], e)
        finally:
            if bank_conn:
                bank_conn.close()

    try:
        lc = get_coordinator_conn()
        with lc.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT tx_id, from_account, to_account, amount, status "
                "FROM transactions "
                "WHERE status IN ('PREPARING','PREPARED','COMMITTING','COMMIT_A','COMPENSATING')"
            )
            for row in cur.fetchall():
                tx_to_accounts[row['tx_id']] = row
                pending_logs.setdefault(
                    row['tx_id'],
                    {
                        'tx_id': row['tx_id'],
                        'xid': None,
                        'phase': row['status'],
                        'amount': row['amount'],
                        'from_account': row.get('from_account'),
                        'to_account': row.get('to_account'),
                    }
                )
                pending_logs[row['tx_id']]['phase'] = row['status']
                pending_logs[row['tx_id']]['amount'] = row['amount']
                if row.get('from_account'):
                    pending_logs[row['tx_id']]['from_account'] = row.get('from_account')
                if row.get('to_account'):
                    pending_logs[row['tx_id']]['to_account'] = row.get('to_account')

            # Với transaction đọc từ participant log (kể cả phase cũ), luôn đối chiếu
            # full trạng thái ở coordinator để tránh recovery lặp sai trên dữ liệu đã kết thúc.
            if pending_logs:
                tx_ids = list(pending_logs.keys())
                placeholders = ', '.join(['%s'] * len(tx_ids))
                cur.execute(
                    "SELECT tx_id, from_account, to_account, amount, status "
                    f"FROM transactions WHERE tx_id IN ({placeholders})",
                    tuple(tx_ids),
                )
                for row in cur.fetchall():
                    tx_to_accounts[row['tx_id']] = row
                    entry = pending_logs.setdefault(
                        row['tx_id'],
                        {
                            'tx_id': row['tx_id'],
                            'xid': None,
                            'phase': row['status'],
                            'amount': row['amount'],
                            'from_account': row.get('from_account'),
                            'to_account': row.get('to_account'),
                        },
                    )
                    if row.get('from_account'):
                        entry['from_account'] = row.get('from_account')
                    if row.get('to_account'):
                        entry['to_account'] = row.get('to_account')
                    if row.get('amount') is not None:
                        entry['amount'] = row.get('amount')
                    if row.get('status'):
                        entry['phase'] = row.get('status')
        lc.close()
    except Exception as e:
        logger.error('[RECOVERY] Lỗi đọc coordinator transactions: %s', e)

    all_tx_ids = set(pending_logs.keys()) | set(tx_to_accounts.keys())
    for tx_id, row in pending_logs.items():
        if row.get('xid'):
            all_tx_ids.add(tx_id)

    if not all_tx_ids and not in_doubt:
        logger.info('[RECOVERY] Không có giao dịch treo.')
        return []

    logger.info('[RECOVERY] Tìm thấy %d giao dịch cần xử lý.', len(all_tx_ids) or len(in_doubt))

    for tx_id in all_tx_ids:
        log_entry = pending_logs.get(tx_id)
        xid = log_entry['xid'] if log_entry else None
        if not xid:
            logger.warning('[RECOVERY] tx=%s thiếu xid, bỏ qua recovery XA.', tx_id)
            continue
        phase = log_entry['phase'] if log_entry else None
        prepared_on = in_doubt.get(xid, [])  # configs còn PREPARED
        tx_meta = tx_to_accounts.get(tx_id, {})
        from_account, to_account = _pick_recovery_accounts(tx_meta, log_entry or {})

        logger.info('[RECOVERY] tx=%s | phase=%s | PREPARED trên %d DB', tx_id, phase, len(prepared_on))

        if _is_terminal_phase_or_status(phase):
            logger.info('[RECOVERY] tx=%s đã ở trạng thái cuối (%s), bỏ qua recovery.', tx_id, phase)
            continue

        # ── Kịch bản 4: Bank A đã COMMIT, Bank B chưa COMMIT ─────────────
        if phase == 'COMMIT_A':
            if prepared_on:
                # Bank B vẫn trong XA PREPARED → có thể hoàn tất COMMIT
                commit_ok = xa_commit(prepared_on[0], xid) if prepared_on else False

                if commit_ok:
                    log_phase(
                        tx_id, xid, 'COMMITTED',
                        {'account_number': from_account} if from_account else None,
                        {'account_number': to_account} if to_account else None,
                        None,
                        None,
                        float(tx_meta.get('amount') or log_entry['amount'] or 0)
                    )
                    _log_recovery_balances(tx_id, from_account, to_account, 'RECOVERY-COMMITTED')
                    recovered.append({'tx_id': tx_id, 'xid': xid, 'action': 'COMMIT_B_COMPLETED'})
                else:
                    # Không COMMIT được → XA ROLLBACK Bank B + Compensation Bank A
                    rollback_xa_all(xid, prepared_on)
                    ok = do_compensation(
                        tx_id, xid,
                        from_account,
                        float(tx_meta.get('amount') or log_entry['amount'] or 0)
                    )
                    _log_recovery_balances(tx_id, from_account, to_account, 'RECOVERY-COMPENSATE')
                    recovered.append({
                        'tx_id': tx_id, 'xid': xid,
                        'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'
                    })
            else:
                # Bank B không còn trong XA RECOVER → bắt buộc Compensation
                logger.warning('[RECOVERY] tx=%s: Bank B mất XA state → thực hiện compensation', tx_id)
                ok = do_compensation(
                    tx_id, xid,
                    from_account,
                    float(tx_meta.get('amount') or log_entry['amount'] or 0)
                )
                _log_recovery_balances(tx_id, from_account, to_account, 'RECOVERY-COMPENSATE')
                recovered.append({
                    'tx_id': tx_id, 'xid': xid,
                    'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'
                })

        # ── Compensation bị gián đoạn → chạy lại ────────────────────────
        elif phase == 'COMPENSATING' and log_entry:
            ok = do_compensation(
                tx_id, xid,
                from_account,
                float(tx_meta.get('amount') or log_entry['amount'] or 0)
            )
            _log_recovery_balances(tx_id, from_account, to_account, 'RECOVERY-COMPENSATE')
            recovered.append({
                'tx_id': tx_id, 'xid': xid,
                'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'
            })

        # ── PREPARED / COMMITTING: sập sau Phase 1 → tiếp tục COMMIT ────
        elif phase in ('PREPARED', 'COMMITTING'):
            for config in prepared_on:
                xa_commit(config, xid)
            log_phase(
                tx_id, xid, 'COMMITTED',
                {'account_number': from_account} if from_account else None,
                {'account_number': to_account} if to_account else None,
                None,
                None,
                float(tx_meta.get('amount') or log_entry['amount'] or 0)
            )
            _log_recovery_balances(tx_id, from_account, to_account, 'RECOVERY-COMMITTED')
            recovered.append({'tx_id': tx_id, 'xid': xid, 'action': 'COMMITTED'})

        # ── PREPARING hoặc không rõ: rollback ────────────────────────────
        else:
            rollback_xa_all(xid, prepared_on)
            if log_entry:
                log_phase(
                    tx_id, xid, 'ABORTED',
                    {'account_number': from_account} if from_account else None,
                    {'account_number': to_account} if to_account else None,
                    None,
                    None,
                    float(tx_meta.get('amount') or log_entry['amount'] or 0)
                )
            _log_recovery_balances(tx_id, from_account, to_account, 'RECOVERY-ABORTED')
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
    log_balance(from_config, from_acc['account_number'], tx_id, 'TRƯỚC')
    log_balance(to_config,   to_acc['account_number'],   tx_id, 'TRƯỚC')
    log_phase(tx_id, xid, 'PREPARING', from_acc, to_acc, from_config, to_config, amount, description)

    # ===== PHASE 1: XA PREPARE — chạy song song, có timeout =====
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_from = executor.submit(
            xa_prepare_participant, from_config, xid, from_acc['account_number'], amount, True)
        future_to = executor.submit(
            xa_prepare_participant, to_config, xid, to_acc['account_number'], amount, False)

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
        log_phase(tx_id, xid, 'TIMEOUT', from_acc, to_acc, from_config, to_config, amount, description)
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
            log_phase(tx_id, xid, 'ABORTED', from_acc, to_acc, from_config, to_config, amount, description)
            rollback_xa_all(xid, [from_config, to_config])
            log_balance(from_config, from_acc['account_number'], tx_id, 'SAU-ABORTED(Phase1)')
            log_balance(to_config,   to_acc['account_number'],   tx_id, 'SAU-ABORTED(Phase1)')
            return (
                False,
                f"Giao dịch thất bại ở Phase 1: {str(exc)}",
                tx_id,
                None
            )

    # ── Cả hai đã PREPARE thành công ───────────────────────────────────
    if has_demo_token(description, TC06_CRASH_BEFORE_COMMIT_TOKEN):
        crash_coordinator_for_demo(
            tx_id,
            'TC06 crash while log is PREPARING, before PREPARED/COMMIT'
        )

    log_phase(tx_id, xid, 'PREPARED', from_acc, to_acc, from_config, to_config, amount, description)

    if has_demo_token(description, TC07_CRASH_AFTER_PREPARE_TOKEN):
        crash_coordinator_for_demo(
            tx_id,
            'TC07 crash after PREPARED, before coordinator decision'
        )

    if has_demo_token(description, TC10_ROLLBACK_TWICE_TOKEN):
        rollback_xa_all(xid, [from_config, to_config])
        rollback_xa_all(xid, [from_config, to_config])
        log_phase(tx_id, xid, 'ABORTED', from_acc, to_acc, from_config, to_config, amount, description)
        return (
            False,
            "TC10 demo: ROLLBACK được gửi 2 lần và hệ thống vẫn xử lý an toàn.",
            tx_id,
            {'demo_case': 'TC10', 'rollback_sent_twice': True}
        )

    # ===== PHASE 2: COMMIT =====
    try:
        log_phase(tx_id, xid, 'COMMITTING', from_acc, to_acc, from_config, to_config, amount, description)

        if has_demo_token(description, TC08_CRASH_DURING_COMMITTING_TOKEN):
            crash_coordinator_for_demo(
                tx_id,
                'TC08 crash while transaction is COMMITTING/in-doubt'
            )

        if has_demo_token(description, TC09_COMMIT_TWICE_TOKEN):
            first_a = xa_commit(from_config, xid)
            first_b = xa_commit(to_config, xid)
            second_a = xa_commit(from_config, xid, tolerate_unknown_xid=True)
            second_b = xa_commit(to_config, xid, tolerate_unknown_xid=True)

            if not (first_a and first_b):
                raise RuntimeError('TC09 demo: initial XA COMMIT failed')

            log_phase(tx_id, xid, 'COMMITTED', from_acc, to_acc, from_config, to_config, amount, description)
            save_transaction(
                tx_id=tx_id,
                from_acc=from_acc,
                to_acc=to_acc,
                amount=amount,
                description=description,
                status='SUCCESS'
            )
            return (
                True,
                "TC09 demo: COMMIT được gửi nhiều lần; lần lặp lại không xử lý trùng.",
                tx_id,
                {
                    'demo_case': 'TC09',
                    'first_commit': {'source': first_a, 'destination': first_b},
                    'repeated_commit': {'source': second_a, 'destination': second_b},
                }
            )

        # Bank A (nguồn) commit trước
        ca = get_connection({**from_config, 'autocommit': True})
        with ca.cursor() as c:
            c.execute(f"XA COMMIT '{xid}'")
        ca.close()

        log_phase(tx_id, xid, 'COMMIT_A', from_acc, to_acc, from_config, to_config, amount, description)
        commit_a_done = True
        log_balance(from_config, from_acc['account_number'], tx_id, 'SAU-COMMIT_A(-trừ)')

        if should_simulate_coordinator_crash_after_commit_a(description):
            crash_coordinator_for_demo(
                tx_id,
                'TC05 crash after COMMIT_A, before COMMIT_B'
            )

        if should_simulate_commit_b_failure(description):
            raise RuntimeError('Bank B commit failed by TC04 demo hook')

        # Bank B (đích) commit
        cb = get_connection({**to_config, 'autocommit': True})
        with cb.cursor() as c:
            c.execute(f"XA COMMIT '{xid}'")
        cb.close()

        log_phase(tx_id, xid, 'COMMITTED', from_acc, to_acc, from_config, to_config, amount, description)
        log_balance(from_config, from_acc['account_number'], tx_id, 'SAU-COMMITTED')
        log_balance(to_config,   to_acc['account_number'],   tx_id, 'SAU-COMMITTED(+nhận)')

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
            log_phase(tx_id, xid, 'ABORTED', from_acc, to_acc, from_config, to_config, amount, description)
            rollback_xa_all(xid, [from_config, to_config])
            return (
                False,
                f"Giao dịch thất bại, đã Rollback: {str(e)}",
                tx_id,
                None
            )
