"""
Transfer routes - /api/transfer
"""

from flask import Blueprint, request, jsonify

from account_service import find_account_by_number
from two_phase_commit import execute_transfer

transfer_bp = Blueprint('transfer', __name__)


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
    data = request.json
    from_account_number = data.get('from_account_number', '')
    to_account_number = data.get('to_account_number', '')
    amount = float(data.get('amount', 0))
    description = data.get('description', '')

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
        "tx_id": tx_id
    }

    if extra_data:
        response.update(extra_data)

    status_code = 200 if success else 500

    # Special case for timeout (408)
    if extra_data and extra_data.get('timeout'):
        status_code = 408

    return jsonify(response), status_code
