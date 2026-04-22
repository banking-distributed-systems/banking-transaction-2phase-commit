"""
Authentication routes - /api/login
"""

from flask import Blueprint, request, jsonify

from account_service import authenticate_user

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/login', methods=['POST'])
def login():
    """
    API đăng nhập
    Request body: {"account_number": "..."}
    """
    data = request.get_json(silent=True) or {}
    account_number = str(data.get('account_number') or '').strip()

    if not account_number:
        return jsonify({
            "status": "error",
            "message": "Vui lòng nhập số tài khoản"
        }), 400

    user = authenticate_user(account_number)

    if user:
        return jsonify({"status": "success", "user": user})

    return jsonify({
        "status": "error",
        "message": "Số tài khoản không tồn tại"
    }), 401
