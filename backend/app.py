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

@app.route('/api/transfer', methods=['POST'])
def transfer():
    data = request.json
    from_account_number = data.get('from_account_number', '')
    to_account_number = data.get('to_account_number', '')
    amount = float(data.get('amount', 0))

    if amount <= 0:
        return jsonify({"status": "error", "message": "Số tiền không hợp lệ"}), 400

    from_acc, from_config = find_account_by_number(from_account_number)
    to_acc, to_config = find_account_by_number(to_account_number)

    if not from_acc:
        return jsonify({"status": "error", "message": "Tài khoản nguồn không tồn tại"}), 400
    if not to_acc:
        return jsonify({"status": "error", "message": "Tài khoản đích không tồn tại"}), 400
    if from_acc['id'] == to_acc['id'] and from_config == to_config:
        return jsonify({"status": "error", "message": "Không thể chuyển tiền cùng một tài khoản"}), 400

    conn_from = get_connection(from_config)
    conn_to = get_connection(to_config)

    xid = str(uuid.uuid4()).replace("-", "")

    try:
        c_from = conn_from.cursor()
        c_to = conn_to.cursor()

        # Phase 1: PREPARE
        c_from.execute(f"XA START '{xid}'")
        c_to.execute(f"XA START '{xid}'")

        c_from.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, from_acc['id']))
        c_to.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, to_acc['id']))

        c_from.execute(f"XA END '{xid}'")
        c_to.execute(f"XA END '{xid}'")

        c_from.execute(f"XA PREPARE '{xid}'")
        c_to.execute(f"XA PREPARE '{xid}'")

        # Phase 2: COMMIT
        c_from.execute(f"XA COMMIT '{xid}'")
        c_to.execute(f"XA COMMIT '{xid}'")

        # Lưu hóa đơn giao dịch vào DB1
        tx_id = 'VB' + xid[:10].upper()
        description = data.get('description', '')
        try:
            conn_log = get_connection({**db1_config, 'autocommit': True})
            with conn_log.cursor() as cur:
                cur.execute(
                    "INSERT INTO transactions (tx_id, from_account_number, from_name, to_account_number, to_name, amount, description, status) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, 'SUCCESS')",
                    (tx_id, from_acc['account_number'], from_acc['name'],
                     to_acc['account_number'], to_acc['name'], amount, description)
                )
            conn_log.close()
        except Exception as log_err:
            print("Lỗi lưu giao dịch:", log_err)

        return jsonify({"status": "success", "message": "Chuyển tiền thành công! (2-Phase Commit Hoàn tất)", "tx_id": tx_id})

    except Exception as e:
        try:
            c_from.execute(f"XA ROLLBACK '{xid}'")
        except: pass
        try:
            c_to.execute(f"XA ROLLBACK '{xid}'")
        except: pass

        return jsonify({"status": "error", "message": f"Giao dịch thất bại, đã Rollback: {str(e)}"}), 500
    finally:
        conn_from.close()
        conn_to.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
