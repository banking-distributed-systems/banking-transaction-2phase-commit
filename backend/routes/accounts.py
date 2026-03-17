"""
Account routes - /api/accounts, /api/lookup-account
"""

from flask import Blueprint, request, jsonify

from account_service import (
    get_all_accounts_with_bank,
    get_account_by_number_safe
)

accounts_bp = Blueprint('accounts', __name__)


@accounts_bp.route('/api/accounts', methods=['GET'])
def get_accounts():
    """
    API lấy danh sách tất cả tài khoản
    """
    accounts = get_all_accounts_with_bank()
    return jsonify(accounts)


@accounts_bp.route('/api/lookup-account', methods=['POST'])
def lookup_account():
    """
    API tra cứu tài khoản theo số tài khoản
    Request body: {"account_number": "..."}
    """
    data = request.json
    account_number = data.get('account_number', '')

    if not account_number:
        return jsonify({
            "status": "error",
            "message": "Vui lòng nhập số tài khoản"
        }), 400

    account = get_account_by_number_safe(account_number)

    if account:
        return jsonify({
            "status": "success",
            "account": account
        })

    return jsonify({
        "status": "error",
        "message": "Không tìm thấy tài khoản"
    }), 404
