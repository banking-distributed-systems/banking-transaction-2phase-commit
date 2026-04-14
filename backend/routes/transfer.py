"""
Transfer routes - /api/transfer
"""

from flask import Blueprint, request, jsonify
import pymysql
from config import PHASE_LABELS

from account_service import find_account_by_number
from database import get_log_conn
from idempotency_service import (
    build_request_hash,
    create_processing_record,
    finalize_record,
    get_idempotency_record,
    parse_stored_response,
)
from two_phase_commit import execute_transfer

transfer_bp = Blueprint('transfer', __name__)


def _build_status_message(phase: str, fallback: str = '') -> str:
    if phase == 'COMMITTED':
        return 'Giao dịch đã hoàn tất thành công.'
    if phase == 'ABORTED':
        return 'Giao dịch đã bị hủy/rollback.'
    if phase == 'COMPENSATED':
        return 'Giao dịch lỗi lệch pha đã được hoàn tiền (compensation).'
    if phase == 'TIMEOUT':
        return 'Giao dịch timeout ở phase prepare.'
    if phase == 'COMMIT_A':
        return 'Đang ở trạng thái lệch pha sau commit A, cần recovery/compensation.'
    return fallback or 'Trạng thái giao dịch đang được cập nhật.'


def _get_transaction_status(tx_id: str):
    conn = None
    try:
        conn = get_log_conn()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tx_id, xid, from_account_number, to_account_number, amount, description, "
                "phase, created_at, updated_at "
                "FROM transaction_log WHERE tx_id = %s",
                (tx_id,),
            )
            row = cur.fetchone()

            if not row:
                return None

            cur.execute(
                "SELECT status FROM transactions WHERE tx_id = %s ORDER BY id DESC LIMIT 1",
                (tx_id,),
            )
            tx_row = cur.fetchone()

        phase = row[6]
        business_status = tx_row[0] if tx_row else None
        return {
            'tx_id': row[0],
            'xid': row[1],
            'from_account_number': row[2],
            'to_account_number': row[3],
            'amount': float(row[4]),
            'description': row[5],
            'phase': phase,
            'phase_label': PHASE_LABELS.get(phase, phase),
            'business_status': business_status,
            'message': _build_status_message(phase),
            'created_at': str(row[7]),
            'updated_at': str(row[8]),
        }
    finally:
        if conn:
            conn.close()


def _get_recent_transactions(limit: int = 10):
    conn = None
    try:
        conn = get_log_conn()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT tx_id, from_account_number, to_account_number, amount, phase, updated_at "
                "FROM transaction_log ORDER BY updated_at DESC LIMIT %s",
                (int(limit),),
            )
            rows = cur.fetchall()

        items = []
        for row in rows:
            phase = row['phase']
            items.append(
                {
                    'tx_id': row['tx_id'],
                    'from_account_number': row['from_account_number'],
                    'to_account_number': row['to_account_number'],
                    'amount': float(row['amount']),
                    'phase': phase,
                    'phase_label': PHASE_LABELS.get(phase, phase),
                    'message': _build_status_message(phase),
                    'updated_at': str(row['updated_at']),
                }
            )
        return items
    finally:
        if conn:
            conn.close()


@transfer_bp.route('/api/transfer', methods=['POST'])
def transfer():
    """
    API chuyển tiền sử dụng Two-Phase Commit
    Request body: {
        "from_account_number": "...",
        "to_account_number": "...",
        "amount": 100000,
        "description": "..."
    }
    """
    data = request.get_json(silent=True) or {}
    from_account_number = str(data.get('from_account_number') or '').strip()
    to_account_number = str(data.get('to_account_number') or '').strip()
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({
            "status": "error",
            "message": "Số tiền không hợp lệ"
        }), 400
    description = str(data.get('description') or '').strip()

    idem_key = str(request.headers.get('Idempotency-Key') or data.get('idempotency_key') or '').strip()
    req_hash = None
    if idem_key:
        req_hash = build_request_hash(
            {
                'from_account_number': from_account_number,
                'to_account_number': to_account_number,
                'amount': amount,
                'description': description,
            }
        )
        existing = get_idempotency_record(idem_key)
        if existing:
            if existing['request_hash'] != req_hash:
                return jsonify(
                    {
                        'status': 'error',
                        'message': 'Idempotency-Key đã được dùng cho payload khác',
                        'error_code': 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD',
                    }
                ), 409

            if existing['status'] == 'PROCESSING':
                return jsonify(
                    {
                        'status': 'error',
                        'message': 'Yêu cầu đang được xử lý, vui lòng thử lại sau',
                        'error_code': 'IDEMPOTENCY_REQUEST_IN_PROGRESS',
                    }
                ), 409

            stored = parse_stored_response(existing)
            if stored is not None:
                stored['idempotent_replay'] = True
                stored['idempotency_key'] = idem_key
                return jsonify(stored), int(existing.get('http_status') or 200)

    # Validation
    if amount <= 0:
        return jsonify({
            "status": "error",
            "message": "Số tiền không hợp lệ"
        }), 400

    # Find accounts
    from_acc, from_config = find_account_by_number(from_account_number)
    to_acc, to_config = find_account_by_number(to_account_number)

    if not from_acc:
        return jsonify({
            "status": "error",
            "message": "Tài khoản nguồn không tồn tại"
        }), 400

    if not to_acc:
        return jsonify({
            "status": "error",
            "message": "Tài khoản đích không tồn tại"
        }), 400

    if from_acc['id'] == to_acc['id'] and from_config == to_config:
        return jsonify({
            "status": "error",
            "message": "Không thể chuyển tiền cùng một tài khoản"
        }), 400

    if idem_key:
        created = create_processing_record(idem_key, req_hash)
        if not created:
            race = get_idempotency_record(idem_key)
            if race:
                if race.get('status') == 'PROCESSING':
                    return jsonify(
                        {
                            'status': 'error',
                            'message': 'Yêu cầu đang được xử lý, vui lòng thử lại sau',
                            'error_code': 'IDEMPOTENCY_REQUEST_IN_PROGRESS',
                        }
                    ), 409
                stored = parse_stored_response(race)
                if stored is not None:
                    stored['idempotent_replay'] = True
                    stored['idempotency_key'] = idem_key
                    return jsonify(stored), int(race.get('http_status') or 200)

    # Execute 2PC transfer
    success, message, tx_id, extra_data = execute_transfer(
        from_acc=from_acc,
        from_config=from_config,
        to_acc=to_acc,
        to_config=to_config,
        amount=amount,
        description=description
    )

    response = {
        "status": "success" if success else "error",
        "message": message,
        "tx_id": tx_id,
        "idempotency_key": idem_key or None
    }

    if extra_data:
        response.update(extra_data)

    status_code = 200 if success else 500

    # Special case for timeout (408)
    if extra_data and extra_data.get('timeout'):
        status_code = 408

    if idem_key:
        finalize_record(idem_key, tx_id, status_code, response, success)

    return jsonify(response), status_code


@transfer_bp.route('/api/transfer/status/<tx_id>', methods=['GET'])
def transfer_status(tx_id: str):
    """Tra cứu trạng thái phase của một transaction theo tx_id."""
    status_data = _get_transaction_status(tx_id)
    if not status_data:
        return jsonify(
            {
                'status': 'error',
                'message': 'Không tìm thấy giao dịch',
                'tx_id': tx_id,
            }
        ), 404

    return jsonify(
        {
            'status': 'success',
            'data': status_data,
        }
    )


@transfer_bp.route('/api/transfer/recent', methods=['GET'])
def transfer_recent():
    """Danh sách giao dịch 2PC gần nhất để hiển thị dashboard monitor."""
    try:
        limit = int(request.args.get('limit', 10))
    except (TypeError, ValueError):
        limit = 10

    limit = max(1, min(limit, 50))
    items = _get_recent_transactions(limit)
    return jsonify({'status': 'success', 'items': items, 'count': len(items)})
