"""
V-Bank 2PC Server - Flask Application
Two-Phase Commit implementation cho giao dịch ngân hàng phân tán
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import time
import uuid
from werkzeug.exceptions import HTTPException

from logger import logger
from routes import register_routes
from two_phase_commit import recover_in_doubt_transactions
from config import DB1_CONFIG, DB2_CONFIG, DB3_CONFIG, ALL_DB_CONFIGS, COORDINATOR_DB_CONFIG
from database import get_connection, get_coordinator_conn, ensure_runtime_schema

# Khởi tạo Flask app
app = Flask(__name__)
CORS(app)
app.config['PROPAGATE_EXCEPTIONS'] = False

_runtime_schema_ready = False

# Đăng ký routes
register_routes(app)


# Middleware đo thời gian xử lý request
@app.before_request
def before_request():
    """Lưu thời gian bắt đầu request"""
    global _runtime_schema_ready
    if not _runtime_schema_ready:
        ensure_runtime_schema()
        _runtime_schema_ready = True

    request.start_time = time.time()
    request.request_id = uuid.uuid4().hex[:12]


@app.after_request
def after_request(response):
    """In thời gian xử lý sau mỗi request"""
    request_id = getattr(request, 'request_id', None)
    if request_id:
        response.headers['X-Request-ID'] = request_id
    if hasattr(request, 'start_time'):
        elapsed = time.time() - request.start_time
        if request_id:
            logger.info(
                f"[TIMING][{request_id}] {request.method} {request.path} - Time: {elapsed:.4f}s"
            )
        else:
            logger.info(f"[TIMING] {request.method} {request.path} - Time: {elapsed:.4f}s")
    return response


def _is_api_request() -> bool:
    return request.path.startswith('/api/')


def _error_payload(status_code: int, message: str, error_code: str, detail: str | None = None):
    payload = {
        'status': 'error',
        'message': message,
        'error': {
            'code': error_code,
            'status_code': status_code,
            'request_id': getattr(request, 'request_id', None)
        }
    }

    if detail and app.debug:
        payload['error']['detail'] = detail

    return payload


@app.errorhandler(HTTPException)
def handle_http_exception(error: HTTPException):
    if not _is_api_request():
        return error

    status_code = error.code or 500
    message = error.description or 'Yêu cầu không hợp lệ'
    error_code = f'HTTP_{status_code}'

    logger.warning(
        '[API ERROR][%s] %s %s -> %s %s',
        getattr(request, 'request_id', '-'),
        request.method,
        request.path,
        status_code,
        message,
    )

    return jsonify(_error_payload(status_code, message, error_code)), status_code


@app.errorhandler(Exception)
def handle_unexpected_exception(error: Exception):
    status_code = 500
    message = 'Lỗi nội bộ hệ thống'
    error_code = 'INTERNAL_SERVER_ERROR'

    logger.exception(
        '[UNHANDLED][%s] %s %s - %s',
        getattr(request, 'request_id', '-'),
        request.method,
        request.path,
        error,
    )

    if _is_api_request():
        return jsonify(_error_payload(status_code, message, error_code, str(error))), status_code

    return jsonify(_error_payload(status_code, message, error_code)), status_code


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

    try:
        conn = get_coordinator_conn()
        conn.close()
        results['Coordinator (coordinator)'] = 'OK'
        logger.info('[STARTUP] ✓ Kết nối Coordinator (coordinator) thành công')
    except Exception as e:
        results['Coordinator (coordinator)'] = f'Lỗi: {e}'
        logger.error('[STARTUP] ✗ Kết nối Coordinator (coordinator) thất bại: %s', e)

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
    logger.info('  🗄  Database:       %s/%s/%s + %s',
                DB1_CONFIG['database'],
                DB2_CONFIG['database'],
                DB3_CONFIG['database'],
                COORDINATOR_DB_CONFIG['database'])
    logger.info('  ⏱  Prepare Timeout: %s giây', 10)
    logger.info('═══════════════════════════════════════════════════════════════')

    app.run(host="0.0.0.0", port=5000, debug=True)

if __name__ == '__main__':
    main()
