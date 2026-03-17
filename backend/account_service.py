"""
Account Service - xử lý các tác vụ liên quan đến tài khoản
"""

import hashlib
from typing import Dict, Any, Optional, List, Tuple

import pymysql

from config import ALL_DB_CONFIGS
from database import get_connection, get_log_conn
from logger import get_logger

logger = get_logger(__name__)


def find_account_by_number(account_number: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Tìm tài khoản theo số tài khoản

    Args:
        account_number: Số tài khoản

    Returns:
        Tuple (account, db_config) hoặc (None, None)
    """
    for config in ALL_DB_CONFIGS:
        try:
            conn = get_connection(config)
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, name, balance, account_number, account_type "
                    "FROM accounts WHERE REPLACE(account_number, ' ', '') = %s",
                    (account_number.replace(' ', ''),)
                )
                acc = cursor.fetchone()
            conn.close()
            if acc:
                return acc, config
        except Exception as e:
            logger.error('[LOOKUP] Lỗi tìm tài khoản: %s', e)
    return None, None


def authenticate_user(phone: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Xác thực người dùng đăng nhập

    Args:
        phone: Số điện thoại
        password: Mật khẩu (plain text)

    Returns:
        Thông tin user nếu đăng nhập thành công, None nếu thất bại
    """
    password_md5 = hashlib.md5(password.encode()).hexdigest()

    for config in ALL_DB_CONFIGS:
        try:
            conn = get_connection(config)
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, name, balance, account_number, account_type "
                    "FROM accounts WHERE phone = %s AND password = %s",
                    (phone, password_md5)
                )
                user = cursor.fetchone()
            conn.close()
            if user:
                return user
        except Exception as e:
            logger.error('[LOGIN] Lỗi kết nối DB: %s', e)

    return None


def save_transaction(
    tx_id: str,
    from_acc: Dict[str, Any],
    to_acc: Dict[str, Any],
    amount: float,
    description: str,
    status: str
) -> bool:
    """
    Lưu giao dịch vào database

    Args:
        tx_id: Transaction ID
        from_acc: Thông tin tài khoản nguồn
        to_acc: Thông tin tài khoản đích
        amount: Số tiền
        description: Mô tả
        status: Trạng thái giao dịch

    Returns:
        True nếu lưu thành công
    """
    try:
        conn_log = get_log_conn()
        with conn_log.cursor() as cur:
            cur.execute(
                "INSERT INTO transactions "
                "(tx_id, from_account_number, from_name, to_account_number, to_name, amount, description, status) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (tx_id, from_acc['account_number'], from_acc['name'],
                 to_acc['account_number'], to_acc['name'], amount, description, status)
            )
        conn_log.close()
        return True
    except Exception as log_err:
        logger.error('[TRANSFER] Lỗi lưu hóa đơn: %s', log_err)
        return False


def get_all_accounts_with_bank() -> List[Dict[str, Any]]:
    """
    Lấy tất cả tài khoản kèm thông tin ngân hàng

    Returns:
        List of accounts với thông tin bank
    """
    accounts = []

    for config in ALL_DB_CONFIGS:
        db_name = config['database']
        bank_label = 'Ngân hàng 1' if db_name == 'bank1' else 'Ngân hàng 2'

        try:
            conn = get_connection(config)
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, name, balance, account_number, account_type, "
                    f"'{bank_label}' as bank FROM accounts"
                )
                accounts.extend(cursor.fetchall())
            conn.close()
        except Exception as e:
            logger.error('[ACCOUNTS] Lỗi kết nối %s: %s', db_name, e)

    return accounts


def get_account_by_number_safe(account_number: str) -> Optional[Dict[str, Any]]:
    """
    Tìm tài khoản và trả về thông tin an toàn (không có sensitive data)

    Args:
        account_number: Số tài khoản

    Returns:
        Thông tin tài khoản (name, account_number) hoặc None
    """
    acc, _ = find_account_by_number(account_number)
    if acc:
        return {
            'name': acc['name'],
            'account_number': acc['account_number']
        }
    return None