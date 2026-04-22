"""
Transfer routes - /api/transfer
"""

from flask import Blueprint, request, jsonify
import pymysql
from config import ALL_DB_CONFIGS, PHASE_LABELS

from account_service import find_account_by_number
from database import get_connection, get_coordinator_conn
from idempotency_service import (
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


def _find_participant_log_by_tx_id(tx_id: str):
    for config in ALL_DB_CONFIGS:
        conn = None
        try:
            conn = get_connection({**config, 'autocommit': True})
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(
                    "SELECT tx_id, xid, phase, amount, created_at "
                    "FROM transaction_log WHERE tx_id = %s",
                    (tx_id,),
                )
                row = cur.fetchone()
                if row:
                    row['bank'] = config['database']
                    return row
        finally:
            if conn:
                conn.close()
    return None


def _get_transaction_status(tx_id: str):
    conn = None
    try:
        conn = get_coordinator_conn()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT tx_id, from_account, to_account, amount, status, created_at "
                "FROM transactions WHERE tx_id = %s",
                (tx_id,),
            )
            row = cur.fetchone()

            if not row:
                return None

        participant_log = _find_participant_log_by_tx_id(tx_id)
        phase = participant_log['phase'] if participant_log else row['status']
        return {
            'tx_id': row['tx_id'],
            'xid': participant_log['xid'] if participant_log else None,
            'from_account_number': row['from_account'],
            'to_account_number': row['to_account'],
            'amount': float(row['amount']),
            'phase': phase,
            'phase_label': PHASE_LABELS.get(phase, phase),
            'business_status': row['status'],
            'message': _build_status_message(phase),
            'created_at': str(row['created_at']),
            'updated_at': str(participant_log['created_at'] if participant_log else row['created_at']),
        }
    finally:
        if conn:
            conn.close()


def _get_recent_transactions(limit: int = 10):
    conn = None
    try:
        conn = get_coordinator_conn()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT tx_id, from_account, to_account, amount, status, created_at "
                "FROM transactions ORDER BY created_at DESC LIMIT %s",
                (int(limit),),
            )
            rows = cur.fetchall()

        items = []
        for row in rows:
            participant_log = _find_participant_log_by_tx_id(row['tx_id'])
            phase = participant_log['phase'] if participant_log else row['status']
            items.append(
                {
                    'tx_id': row['tx_id'],
                    'from_account_number': row['from_account'],
                    'to_account_number': row['to_account'],
                    'amount': float(row['amount']),
                    'phase': phase,
                    'phase_label': PHASE_LABELS.get(phase, phase),
                    'message': _build_status_message(phase),
                    'updated_at': str(participant_log['created_at'] if participant_log else row['created_at']),
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
    if idem_key:
        existing = get_idempotency_record(idem_key)
        if existing:
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
                return jsonify(stored), 200
            if existing.get('tx_id'):
                return jsonify(
                    {
                        'status': 'success' if existing['status'] == 'COMPLETED' else 'error',
                        'message': 'Yêu cầu trước đó đã được xử lý.',
                        'tx_id': existing['tx_id'],
                        'idempotent_replay': True,
                        'idempotency_key': idem_key,
                    }
                ), 200 if existing['status'] == 'COMPLETED' else 409

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

    if from_acc['account_number'] == to_acc['account_number'] and from_config == to_config:
        return jsonify({
            "status": "error",
            "message": "Không thể chuyển tiền cùng một tài khoản"
        }), 400

    if idem_key:
        created = create_processing_record(idem_key)
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
                    return jsonify(stored), 200
                if race.get('tx_id'):
                    return jsonify(
                        {
                            'status': 'success' if race['status'] == 'COMPLETED' else 'error',
                            'message': 'Yêu cầu trước đó đã được xử lý.',
                            'tx_id': race['tx_id'],
                            'idempotent_replay': True,
                            'idempotency_key': idem_key,
                        }
                    ), 200 if race['status'] == 'COMPLETED' else 409

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
        finalize_record(idem_key, tx_id, success)

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


@transfer_bp.route('/api/transfer/log/<tx_id>', methods=['GET'])
def transfer_tx_log(tx_id: str):
    """Đọc log lines liên quan đến tx_id từ .log file tại project root."""
    import os as _os
    log_path = _os.path.normpath(
        _os.path.join(_os.path.dirname(__file__), '..', '..', '.log')
    )
    lines = []
    if _os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if tx_id in line:
                        lines.append(line.rstrip('\n\r'))
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'success', 'tx_id': tx_id, 'lines': lines, 'count': len(lines)})
