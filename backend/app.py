import uuid
import hashlib
import pymysql
import concurrent.futures
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Thời gian chờ tối đa (giây) cho Phase 1 (PREPARE) — Kịch bản 5
PREPARE_TIMEOUT = 10

# connect_timeout: thời gian tối đa thiết lập kết nối
# read_timeout / write_timeout: thời gian tối đa chờ phản hồi từ DB
db1_config = {
    'host': 'localhost', 'port': 5433, 'user': 'root', 'password': 'root',
    'database': 'bank1', 'autocommit': False,
    'connect_timeout': 5, 'read_timeout': 8, 'write_timeout': 8
}
db2_config = {
    'host': 'localhost', 'port': 5434, 'user': 'root', 'password': 'root',
    'database': 'bank2', 'autocommit': False,
    'connect_timeout': 5, 'read_timeout': 8, 'write_timeout': 8
}

def get_connection(config):
    return pymysql.connect(**config)

def get_log_conn():
    """Kết nối autocommit tới DB1 để ghi transaction_log"""
    return get_connection({**db1_config, 'autocommit': True})

def log_phase(tx_id, xid, phase, from_acc=None, to_acc=None, amount=None, description=''):
    """Ghi / cập nhật trạng thái phase vào transaction_log"""
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
                     to_acc['account_number'],   to_acc['name'],
                     amount, description)
                )
            else:
                cur.execute(
                    "UPDATE transaction_log SET phase=%s WHERE tx_id=%s",
                    (phase, tx_id)
                )
        conn.close()
    except Exception as e:
        print(f"[LOG] Lỗi ghi transaction_log ({phase}):", e)

# ---------------------------------------------------------------------------
# Compensating Transaction — Kịch bản 4
# ---------------------------------------------------------------------------
def _do_compensation(tx_id, xid, from_account_number, amount):
    """
    Bank A đã COMMIT (tiền đã trừ) nhưng Bank B chưa COMMIT.
    Tạo giao dịch bù: cộng lại số tiền cho tài khoản nguồn (Bank A).
    """
    print(f"[COMPENSATE] Bắt đầu hoàn tiền cho giao dịch {tx_id} ...")
    from_acc, from_conf = find_account_by_number(from_account_number)
    if not from_acc:
        print(f"[COMPENSATE] Không tìm thấy tài khoản nguồn {from_account_number}")
        return False
    try:
        log_phase(tx_id, xid, 'COMPENSATING')
        conn = get_connection({**from_conf, 'autocommit': True})
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE accounts SET balance = balance + %s WHERE id = %s",
                (amount, from_acc['id'])
            )
        conn.close()
        log_phase(tx_id, xid, 'COMPENSATED')
        print(f"[COMPENSATE] Đã hoàn {amount:,.0f}đ → tài khoản {from_account_number}")
        # Lưu dấu vết vào bảng transactions
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
            print(f"[COMPENSATE] Lỗi ghi transactions: {log_err}")
        return True
    except Exception as e:
        print(f"[COMPENSATE] Lỗi thực hiện compensation {tx_id}: {e}")
        return False

# ---------------------------------------------------------------------------
# Recovery: chạy khi TC khởi động lại
# ---------------------------------------------------------------------------
def recover_in_doubt_transactions():
    """
    Quét XA transactions đang PREPARED và log entries chưa hoàn tất.
    Xử lý từng kịch bản:
      PREPARING          → XA ROLLBACK (sập trước khi PREPARE hoàn tất)
      PREPARED/COMMITTING → XA COMMIT tất cả participant còn PREPARED
      COMMIT_A           → XA COMMIT Bank B nếu còn PREPARED; nếu không → Compensation
      COMPENSATING       → Chạy lại compensation bị gián đoạn
    """
    print("[RECOVERY] Bắt đầu kiểm tra giao dịch treo...")
    recovered = []

    # Bước 1: XA RECOVER — map xid → list configs còn PREPARED
    in_doubt = {}
    for config in [db1_config, db2_config]:
        try:
            conn = get_connection({**config, 'autocommit': True})
            with conn.cursor() as cur:
                cur.execute("XA RECOVER")
                for row in cur.fetchall():
                    xid = row[3]
                    in_doubt.setdefault(xid, []).append(config)
            conn.close()
        except Exception as e:
            print("[RECOVERY] Lỗi XA RECOVER:", e)

    # Bước 2: đọc tất cả log entry chưa kết thúc
    # (bao gồm COMMIT_A — Bank A đã commit, có thể không còn trong XA RECOVER)
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
        print("[RECOVERY] Lỗi đọc transaction_log:", e)
        pending_logs = {}

    all_xids = set(in_doubt.keys()) | set(pending_logs.keys())

    if not all_xids:
        print("[RECOVERY] Không có giao dịch treo.")
        return []

    print(f"[RECOVERY] Tìm thấy {len(all_xids)} giao dịch cần xử lý.")

    for xid in all_xids:
        log_entry   = pending_logs.get(xid)
        phase       = log_entry['phase'] if log_entry else None
        tx_id       = log_entry['tx_id'] if log_entry else xid
        prepared_on = in_doubt.get(xid, [])  # configs còn PREPARED

        print(f"[RECOVERY] {tx_id}: phase={phase}, PREPARED trên {len(prepared_on)} DB")

        # ── Kịch bản 4: Bank A đã COMMIT, Bank B chưa COMMIT ─────────────
        if phase == 'COMMIT_A':
            if prepared_on:
                # Bank B vẫn trong XA PREPARED → có thể hoàn tất COMMIT
                commit_ok = False
                for config in prepared_on:
                    try:
                        conn = get_connection({**config, 'autocommit': True})
                        with conn.cursor() as cur:
                            cur.execute(f"XA COMMIT '{xid}'")
                        conn.close()
                        commit_ok = True
                        print(f"[RECOVERY] {tx_id}: Hoàn tất XA COMMIT Bank B → COMMITTED")
                    except Exception as e:
                        print(f"[RECOVERY] Lỗi XA COMMIT Bank B: {e}")

                if commit_ok:
                    log_phase(tx_id, xid, 'COMMITTED')
                    recovered.append({'tx_id': tx_id, 'xid': xid, 'action': 'COMMIT_B_COMPLETED'})
                else:
                    # Không COMMIT được → XA ROLLBACK Bank B + Compensation Bank A
                    for config in prepared_on:
                        try:
                            conn = get_connection({**config, 'autocommit': True})
                            with conn.cursor() as cur:
                                cur.execute(f"XA ROLLBACK '{xid}'")
                            conn.close()
                        except: pass
                    ok = _do_compensation(tx_id, xid,
                                          log_entry['from_account_number'],
                                          float(log_entry['amount']))
                    recovered.append({'tx_id': tx_id, 'xid': xid,
                                      'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'})
            else:
                # Bank B không còn trong XA RECOVER (DB mất prepared state)
                # Bank A đã commit rồi → bắt buộc Compensation
                print(f"[RECOVERY] {tx_id}: Bank B mất XA state → thực hiện compensation")
                ok = _do_compensation(tx_id, xid,
                                      log_entry['from_account_number'],
                                      float(log_entry['amount']))
                recovered.append({'tx_id': tx_id, 'xid': xid,
                                  'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'})

        # ── Compensation bị gián đoạn → chạy lại ────────────────────────
        elif phase == 'COMPENSATING' and log_entry:
            ok = _do_compensation(tx_id, xid,
                                  log_entry['from_account_number'],
                                  float(log_entry['amount']))
            recovered.append({'tx_id': tx_id, 'xid': xid,
                              'action': 'COMPENSATED' if ok else 'COMPENSATION_FAILED'})

        # ── PREPARED / COMMITTING: sập sau Phase 1 → tiếp tục COMMIT ────
        elif phase in ('PREPARED', 'COMMITTING'):
            for config in prepared_on:
                try:
                    conn = get_connection({**config, 'autocommit': True})
                    with conn.cursor() as cur:
                        cur.execute(f"XA COMMIT '{xid}'")
                    conn.close()
                except Exception as e:
                    print(f"[RECOVERY] Lỗi XA COMMIT ({config['database']}): {e}")
            log_phase(tx_id, xid, 'COMMITTED')
            recovered.append({'tx_id': tx_id, 'xid': xid, 'action': 'COMMITTED'})

        # ── PREPARING hoặc không rõ: rollback ────────────────────────────
        else:
            for config in prepared_on:
                try:
                    conn = get_connection({**config, 'autocommit': True})
                    with conn.cursor() as cur:
                        cur.execute(f"XA ROLLBACK '{xid}'")
                    conn.close()
                except Exception as e:
                    print(f"[RECOVERY] Lỗi XA ROLLBACK ({config['database']}): {e}")
            if log_entry:
                log_phase(tx_id, xid, 'ABORTED')
            recovered.append({'tx_id': tx_id, 'xid': xid, 'action': 'ABORTED'})

    return recovered


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    phone = data.get('phone', '')
    password = data.get('password', '')
    password_md5 = hashlib.md5(password.encode()).hexdigest()

    configs = [db1_config, db2_config]
    for config in configs:
        try:
            conn = get_connection(config)
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, name, balance, account_number, account_type FROM accounts WHERE phone = %s AND password = %s",
                    (phone, password_md5)
                )
                user = cursor.fetchone()
            conn.close()
            if user:
                return jsonify({"status": "success", "user": user})
        except Exception as e:
            print("Lỗi login:", e)

    return jsonify({"status": "error", "message": "Số điện thoại hoặc mật khẩu không đúng"}), 401

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    accounts = []
    
    try:
        conn1 = get_connection(db1_config)
        with conn1.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT id, name, balance, account_number, account_type, 'Ngân hàng 1' as bank FROM accounts")
            accounts.extend(cursor.fetchall())
        conn1.close()
    except Exception as e:
        print("Lỗi kết nối DB1:", e)

    try:
        conn2 = get_connection(db2_config)
        with conn2.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT id, name, balance, account_number, account_type, 'Ngân hàng 2' as bank FROM accounts")
            accounts.extend(cursor.fetchall())
        conn2.close()
    except Exception as e:
        print("Lỗi kết nối DB2:", e)

    return jsonify(accounts)

def find_account_by_number(account_number):
    """Tìm tài khoản theo số tài khoản, trả về (account, db_config) hoặc (None, None)"""
    configs = [db1_config, db2_config]
    for config in configs:
        try:
            conn = get_connection(config)
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, name, balance, account_number, account_type FROM accounts WHERE REPLACE(account_number, ' ', '') = %s",
                    (account_number.replace(' ', ''),)
                )
                acc = cursor.fetchone()
            conn.close()
            if acc:
                return acc, config
        except Exception as e:
            print("Lỗi lookup:", e)
    return None, None

def _xa_prepare_participant(config, xid, account_id, amount, is_debit):
    """
    Worker ch\u1ea1y trong thread ri\u00eang (Phase 1).
    Th\u1ef1c hi\u1ec7n: XA START \u2192 UPDATE balance \u2192 XA END \u2192 XA PREPARE.
    Sau PREPARE, XA state t\u1ed3n t\u1ea1i tr\u00ean MySQL server \u2014 connection c\u00f3 th\u1ec3 \u0111\u00f3ng.
    N\u1ebfu DB ph\u1ea3n h\u1ed3i ch\u1eadm qu\u00e1 read_timeout \u2192 pymysql t\u1ef1 raise OperationalError.
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
        conn.close()  # XA PREPARED \u2014 state \u0111\u01b0\u1ee3c gi\u1eef b\u1edfi MySQL, kh\u00f4ng ph\u1ea3i connection

@app.route('/api/lookup-account', methods=['POST'])
def lookup_account():
    data = request.json
    account_number = data.get('account_number', '')
    if not account_number:
        return jsonify({"status": "error", "message": "Vui lòng nhập số tài khoản"}), 400

    acc, _ = find_account_by_number(account_number)
    if acc:
        return jsonify({"status": "success", "account": {"name": acc['name'], "account_number": acc['account_number']}})
    return jsonify({"status": "error", "message": "Không tìm thấy tài khoản"}), 404

@app.route('/api/recover', methods=['POST'])
def manual_recover():
    """API kích hoạt recovery thủ công"""
    result = recover_in_doubt_transactions()
    return jsonify({
        "status": "success",
        "recovered": result,
        "count": len(result)
    })

@app.route('/api/transfer', methods=['POST'])
def transfer():
    data = request.json
    from_account_number = data.get('from_account_number', '')
    to_account_number   = data.get('to_account_number', '')
    amount              = float(data.get('amount', 0))
    description         = data.get('description', '')

    if amount <= 0:
        return jsonify({"status": "error", "message": "S\u1ed1 ti\u1ec1n kh\u00f4ng h\u1ee3p l\u1ec7"}), 400

    from_acc, from_config = find_account_by_number(from_account_number)
    to_acc,   to_config   = find_account_by_number(to_account_number)

    if not from_acc:
        return jsonify({"status": "error", "message": "T\u00e0i kho\u1ea3n ngu\u1ed3n kh\u00f4ng t\u1ed3n t\u1ea1i"}), 400
    if not to_acc:
        return jsonify({"status": "error", "message": "T\u00e0i kho\u1ea3n \u0111\u00edch kh\u00f4ng t\u1ed3n t\u1ea1i"}), 400
    if from_acc['id'] == to_acc['id'] and from_config == to_config:
        return jsonify({"status": "error", "message": "Kh\u00f4ng th\u1ec3 chuy\u1ec3n ti\u1ec1n c\u00f9ng m\u1ed9t t\u00e0i kho\u1ea3n"}), 400

    xid   = str(uuid.uuid4()).replace("-", "")
    tx_id = 'VB' + xid[:10].upper()
    commit_a_done = False

    def _rollback_xa():
        """Rollback XA tr\u00ean c\u1ea3 hai DB b\u1eb1ng k\u1ebft n\u1ed1i m\u1edbi (b\u1ecf qua l\u1ed7i n\u1ebfu XA ch\u01b0a t\u1ed3n t\u1ea1i)."""
        for cfg in [from_config, to_config]:
            try:
                rc = get_connection({**cfg, 'autocommit': True})
                with rc.cursor() as c:
                    c.execute(f"XA ROLLBACK '{xid}'")
                rc.close()
            except: pass

    # Ghi log: PREPARING
    log_phase(tx_id, xid, 'PREPARING', from_acc, to_acc, amount, description)

    # ===== PHASE 1: XA PREPARE \u2014 ch\u1ea1y song song, c\u00f3 timeout (K\u1ecbch b\u1ea3n 5) =====
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_from = executor.submit(
            _xa_prepare_participant, from_config, xid, from_acc['id'], amount, True)
        future_to = executor.submit(
            _xa_prepare_participant, to_config,   xid, to_acc['id'],   amount, False)

        done, pending = concurrent.futures.wait(
            [future_from, future_to], timeout=PREPARE_TIMEOUT)

    # \u2500\u2500 Ki\u1ec3m tra timeout \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if pending:
        slow = []
        if future_from in pending: slow.append('Bank A (ngu\u1ed3n)')
        if future_to   in pending: slow.append('Bank B (\u0111\u00edch)')
        slow_str = ', '.join(slow)
        print(f"[TIMEOUT] {tx_id}: {slow_str} kh\u00f4ng ph\u1ea3n h\u1ed3i PREPARE sau {PREPARE_TIMEOUT}s")
        log_phase(tx_id, xid, 'TIMEOUT')
        _rollback_xa()
        return jsonify({
            "status":  "error",
            "message": (f"K\u1ecbch b\u1ea3n 5 \u2014 Timeout: {slow_str} kh\u00f4ng ph\u1ea3n h\u1ed3i "
                        f"trong {PREPARE_TIMEOUT}s. \u0110\u00e3 t\u1ef1 \u0111\u1ed9ng h\u1ee7y giao d\u1ecbch, "
                        f"kh\u00f4ng t\u00e0i kho\u1ea3n n\u00e0o thay \u0111\u1ed5i s\u1ed1 d\u01b0."),
            "timeout": True,
            "tx_id":   tx_id
        }), 408

    # \u2500\u2500 Ki\u1ec3m tra l\u1ed7i t\u1eeb c\u00e1c future \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    for future in [future_from, future_to]:
        exc = future.exception()
        if exc is not None:
            log_phase(tx_id, xid, 'ABORTED')
            _rollback_xa()
            return jsonify({"status": "error",
                            "message": f"Giao d\u1ecbch th\u1ea5t b\u1ea1i \u1edf Phase 1: {str(exc)}"}), 500

    # \u2500\u2500 C\u1ea3 hai \u0111\u00e3 PREPARE th\u00e0nh c\u00f4ng \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    log_phase(tx_id, xid, 'PREPARED')

    # ===== PHASE 2: COMMIT =====
    try:
        log_phase(tx_id, xid, 'COMMITTING')

        # Bank A (ngu\u1ed3n) commit tr\u01b0\u1edbc \u2014 d\u00f9ng k\u1ebft n\u1ed1i m\u1edbi (Phase 1 \u0111\u00e3 \u0111\u00f3ng)
        ca = get_connection({**from_config, 'autocommit': True})
        with ca.cursor() as c: c.execute(f"XA COMMIT '{xid}'")
        ca.close()

        log_phase(tx_id, xid, 'COMMIT_A')
        commit_a_done = True

        # Bank B (\u0111\u00edch) commit
        cb = get_connection({**to_config, 'autocommit': True})
        with cb.cursor() as c: c.execute(f"XA COMMIT '{xid}'")
        cb.close()

        log_phase(tx_id, xid, 'COMMITTED')

        # L\u01b0u h\u00f3a \u0111\u01a1n
        try:
            conn_log = get_log_conn()
            with conn_log.cursor() as cur:
                cur.execute(
                    "INSERT INTO transactions "
                    "(tx_id, from_account_number, from_name, to_account_number, to_name, amount, description, status) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,'SUCCESS')",
                    (tx_id, from_acc['account_number'], from_acc['name'],
                     to_acc['account_number'], to_acc['name'], amount, description)
                )
            conn_log.close()
        except Exception as log_err:
            print("L\u1ed7i l\u01b0u h\u00f3a \u0111\u01a1n:", log_err)

        return jsonify({"status": "success",
                        "message": "Chuy\u1ec3n ti\u1ec1n th\u00e0nh c\u00f4ng! (2-Phase Commit Ho\u00e0n t\u1ea5t)",
                        "tx_id": tx_id})

    except Exception as e:
        if commit_a_done:
            # K\u1ecbch b\u1ea3n 4: Bank A \u0111\u00e3 COMMIT, Bank B ch\u01b0a
            print(f"[PARTIAL COMMIT] {tx_id}: Bank A committed, Bank B failed \u2192 compensation")
            try:
                rc = get_connection({**to_config, 'autocommit': True})
                with rc.cursor() as c: c.execute(f"XA ROLLBACK '{xid}'")
                rc.close()
            except Exception as rb_err:
                print(f"[PARTIAL COMMIT] XA ROLLBACK Bank B th\u1ea5t b\u1ea1i: {rb_err}")

            ok = _do_compensation(tx_id, xid, from_acc['account_number'], amount)
            return jsonify({
                "status":  "error",
                "message": ("L\u1ed7i COMMIT l\u1ec7ch pha (K\u1ecbch b\u1ea3n 4): "
                            "Bank A \u0111\u00e3 tr\u1eeb ti\u1ec1n nh\u01b0ng Bank B ch\u01b0a nh\u1eadn. "
                            + ("\u0110\u00e3 ho\u00e0n ti\u1ec1n t\u1ef1 \u0111\u1ed9ng cho ng\u01b0\u1eddi g\u1eedi." if ok
                               else "C\u1ea2NH B\u00c1O: Ho\u00e0n ti\u1ec1n th\u1ea5t b\u1ea1i \u2014 c\u1ea7n x\u1eed l\u00fd th\u1ee7 c\u00f4ng!")),
                "partial_failure": True,
                "compensation": ok,
                "tx_id": tx_id
            }), 500
        else:
            log_phase(tx_id, xid, 'ABORTED')
            _rollback_xa()
            return jsonify({"status": "error",
                            "message": f"Giao d\u1ecbch th\u1ea5t b\u1ea1i, \u0111\u00e3 Rollback: {str(e)}"}), 500

if __name__ == '__main__':
    # Chạy recovery trước khi server nhận request mới
    try:
        recover_in_doubt_transactions()
    except Exception as e:
        print("[RECOVERY] Không thể chạy recovery khi khởi động:", e)
    app.run(debug=True, port=5000)
