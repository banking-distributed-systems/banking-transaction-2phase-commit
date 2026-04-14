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
    data = request.get_json(silent=True) or {}
    phone = str(data.get('phone') or '').strip()
    password = str(data.get('password') or '').strip()

    if not phone:
        return jsonify({
            "status": "error",
            "message": "Vui lòng nhập số điện thoại"
        }), 400

    if not password:
        return jsonify({
            "status": "error",
            "message": "Vui lòng nhập mật khẩu"
        }), 400

    user = authenticate_user(phone, password)

    if user:
        return jsonify({"status": "success", "user": user})

    return jsonify({
        "status": "error",
        "message": "Số điện thoại hoặc mật khẩu không đúng"
    }), 401
