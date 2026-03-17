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
    Request body: {"phone": "...", "password": "..."}
    """
    data = request.json
    phone = data.get('phone', '')
    password = data.get('password', '')

    user = authenticate_user(phone, password)

    if user:
        return jsonify({"status": "success", "user": user})

    return jsonify({
        "status": "error",
        "message": "Số điện thoại hoặc mật khẩu không đúng"
    }), 401
