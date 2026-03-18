"""
V-Bank 2PC Server - Flask Application
Two-Phase Commit implementation cho giao dịch ngân hàng phân tán
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import time

from logger import logger
from routes import register_routes
from two_phase_commit import recover_in_doubt_transactions
from config import DB1_CONFIG, DB2_CONFIG, DB3_CONFIG, ALL_DB_CONFIGS
from database import get_connection

# Khởi tạo Flask app
app = Flask(__name__)
CORS(app)

# Đăng ký routes
register_routes(app)


# Middleware đo thời gian xử lý request
@app.before_request
def before_request():
    """Lưu thời gian bắt đầu request"""
    request.start_time = time.time()


@app.after_request
def after_request(response):
    """In thời gian xử lý sau mỗi request"""
    if hasattr(request, 'start_time'):
        elapsed = time.time() - request.start_time
        logger.info(f"[TIMING] {request.method} {request.path} - Time: {elapsed:.4f}s")
    return response


@app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "V-Bank 2PC Server is running"})


def check_database_connections():
    """Kiểm tra kết nối database khi khởi động"""
    results = {}
    db_names = {
        id(DB1_CONFIG): 'Bank A (bank1)',
        id(DB2_CONFIG): 'Bank B (bank2)',
        id(DB3_CONFIG): 'Bank C (bank3)'
    }

    for config in ALL_DB_CONFIGS:
        db_name = db_names.get(id(config), 'Unknown')
        try:
            conn = get_connection(config)
            conn.close()
            results[db_name] = 'OK'
            logger.info('[STARTUP] ✓ Kết nối %s thành công', db_name)
        except Exception as e:
            results[db_name] = f'Lỗi: {e}'
            logger.error('[STARTUP] ✗ Kết nối %s thất bại: %s', db_name, e)

    return results

@app.route('/api/health')
def api_health():
    return jsonify({
        "status": "ok",
        "message": "API is running"
    })

def main():
    """Entry point cho pip install"""
    logger.info('═══════════════════════════════════════════════════════════════')
    logger.info('              V-Bank 2PC Server đang khởi động...              ')
    logger.info('═══════════════════════════════════════════════════════════════')

    # Kiểm tra kết nối database
    logger.info('[STARTUP] Đang kiểm tra kết nối database...')
    db_status = check_database_connections()

    # Chạy recovery khi khởi động
    logger.info('[STARTUP] Đang chạy recovery cho các giao dịch treo...')
    try:
        recovered = recover_in_doubt_transactions()
        if recovered:
            logger.info('[STARTUP] ✓ Đã khôi phục %d giao dịch treo', len(recovered))
        else:
            logger.info('[STARTUP] ✓ Không có giao dịch treo nào')
    except Exception as e:
        logger.error('[STARTUP] ✗ Không thể chạy recovery khi khởi động: %s', e)

    # Hiển thị thông tin server
    logger.info('═══════════════════════════════════════════════════════════════')
    logger.info('  🎉 V-Bank 2PC Server khởi động thành công!')
    logger.info('  📍 Server chạy tại: http://localhost:5000')
    logger.info('  📍 API Base URL:    http://localhost:5000/api')
    logger.info('  🗄  Database:       %s/%s/%s',
                DB1_CONFIG['database'],
                DB2_CONFIG['database'],
                DB3_CONFIG['database'])
    logger.info('  ⏱  Prepare Timeout: %s giây', 10)
    logger.info('═══════════════════════════════════════════════════════════════')

    app.run(host="0.0.0.0", port=5000, debug=True)

if __name__ == '__main__':
    main()
