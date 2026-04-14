"""
Recovery routes - /api/recover
"""

from flask import Blueprint, jsonify

from two_phase_commit import recover_in_doubt_transactions

recovery_bp = Blueprint('recovery', __name__)


@recovery_bp.route('/api/recover', methods=['POST'])
def manual_recover():
    """
    API kích hoạt recovery thủ công cho các giao dịch treo
    """
    result = recover_in_doubt_transactions()
    return jsonify({
        "status": "success",
        "recovered": result,
        "count": len(result)
    })
