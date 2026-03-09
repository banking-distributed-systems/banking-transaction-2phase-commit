import uuid
import hashlib
import pymysql
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

db1_config = {'host': 'localhost', 'port': 5433, 'user': 'root', 'password': 'root', 'database': 'bank1', 'autocommit': False}
db2_config = {'host': 'localhost', 'port': 5434, 'user': 'root', 'password': 'root', 'database': 'bank2', 'autocommit': False}

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
        return jsonify({"status": "error", "message": "Số tiền không hợp lệ"}), 400

    from_acc, from_config = find_account_by_number(from_account_number)
    to_acc,   to_config   = find_account_by_number(to_account_number)

    if not from_acc:
        return jsonify({"status": "error", "message": "Tài khoản nguồn không tồn tại"}), 400
    if not to_acc:
        return jsonify({"status": "error", "message": "Tài khoản đích không tồn tại"}), 400
    if from_acc['id'] == to_acc['id'] and from_config == to_config:
        return jsonify({"status": "error", "message": "Không thể chuyển tiền cùng một tài khoản"}), 400

    xid   = str(uuid.uuid4()).replace("-", "")
    tx_id = 'VB' + xid[:10].upper()
    commit_a_done = False  # Cờ theo dõi: Bank A đã commit trong Phase 2 chưa

    conn_from = get_connection(from_config)
    conn_to   = get_connection(to_config)

    try:
        c_from = conn_from.cursor()
        c_to   = conn_to.cursor()

        # --- Ghi log: PREPARING (trước khi thực hiện bất kỳ thẩm vấn nào) ---
        log_phase(tx_id, xid, 'PREPARING', from_acc, to_acc, amount, description)

        # ===== PHASE 1: START + UPDATE + PREPARE =====
        c_from.execute(f"XA START '{xid}'")
        c_to.execute(f"XA START '{xid}'")

        c_from.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_acc['id']))
        c_to.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_acc['id']))

        c_from.execute(f"XA END '{xid}'")
        c_to.execute(f"XA END '{xid}'")

        c_from.execute(f"XA PREPARE '{xid}'")
        c_to.execute(f"XA PREPARE '{xid}'")

        # --- Ghi log: PREPARED (cả hai participant đã sẵn sàng) ---
        # Nếu TC sập sau đây → recovery sẽ thấy PREPARED → tự COMMIT lại
        log_phase(tx_id, xid, 'PREPARED')

        # ===== PHASE 2: COMMIT =====
        # Ghi nhận TC bắt đầu Phase 2; recovery sẽ dùng phase này
        log_phase(tx_id, xid, 'COMMITTING')

        # Bank A (nguồn) commit trước
        c_from.execute(f"XA COMMIT '{xid}'")
        # *** Nếu TC sập ngay đây → phase = COMMIT_A trong log ***
        # *** Recovery sẽ phát hiện và hoàn tất hoặc bù giao dịch ***
        log_phase(tx_id, xid, 'COMMIT_A')
        commit_a_done = True   # Bank A đã commit thành công

        # Bank B (đích) commit
        c_to.execute(f"XA COMMIT '{xid}'")

        # --- Ghi log: COMMITTED ---
        log_phase(tx_id, xid, 'COMMITTED')

        # Lưu hóa đơn vào bảng transactions
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
            print("Lỗi lưu hóa đơn:", log_err)

        return jsonify({"status": "success",
                        "message": "Chuyển tiền thành công! (2-Phase Commit Hoàn tất)",
                        "tx_id": tx_id})

    except Exception as e:
        if commit_a_done:
            # ───────────────────────────────────────────────────────────────
            # KỊCH BẢN 4: Bank A đã COMMIT, Bank B chưa COMMIT
            # XA ROLLBACK Bank A không còn hiệu lực → phải dùng Compensating Transaction
            # ───────────────────────────────────────────────────────────────
            print(f"[PARTIAL COMMIT] {tx_id}: Bank A committed, Bank B failed → compensation")

            # Thử XA ROLLBACK Bank B (nếu vẫn còn trong PREPARED state)
            try:
                c_to.execute(f"XA ROLLBACK '{xid}'")
                print(f"[PARTIAL COMMIT] XA ROLLBACK Bank B thành công")
            except Exception as rb_err:
                print(f"[PARTIAL COMMIT] XA ROLLBACK Bank B thất bại: {rb_err}")

            # Thực hiện giao dịch bù cho Bank A
            ok = _do_compensation(tx_id, xid, from_acc['account_number'], amount)

            return jsonify({
                "status": "error",
                "message": (
                    "Lỗi COMMIT lệch pha (Kịch bản 4): "
                    "Bank A đã trừ tiền nhưng Bank B chưa nhận. "
                    + ("Đã hoàn tiền tự động cho người gửi." if ok
                       else "CẢNH BÁO: Hoàn tiền thất bại — cần xử lý thủ công!")
                ),
                "partial_failure": True,
                "compensation": ok,
                "tx_id": tx_id
            }), 500
        else:
            # Lỗi trong Phase 1 → XA ROLLBACK bình thường
            log_phase(tx_id, xid, 'ABORTED')
            try:
                c_from.execute(f"XA ROLLBACK '{xid}'")
            except: pass
            try:
                c_to.execute(f"XA ROLLBACK '{xid}'")
            except: pass
            return jsonify({"status": "error",
                            "message": f"Giao dịch thất bại, đã Rollback: {str(e)}"}), 500
    finally:
        conn_from.close()
        conn_to.close()

if __name__ == '__main__':
    # Chạy recovery trước khi server nhận request mới
    try:
        recover_in_doubt_transactions()
    except Exception as e:
        print("[RECOVERY] Không thể chạy recovery khi khởi động:", e)
    app.run(debug=True, port=5000)
