"""
Account Service - xử lý các tác vụ liên quan đến tài khoản
"""

from typing import Dict, Any, Optional, List, Tuple

import pymysql

from config import ALL_DB_CONFIGS
from database import get_connection, get_coordinator_conn
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
    normalized_account_number = str(account_number or '').strip().replace(' ', '')
    if not normalized_account_number:
        return None, None

    for config in ALL_DB_CONFIGS:
        try:
            conn = get_connection(config)
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT name, balance, account_number, account_type "
                    "FROM accounts WHERE REPLACE(account_number, ' ', '') = %s",
                    (normalized_account_number,)
                )
                acc = cursor.fetchone()
            conn.close()
            if acc:
                return acc, config
        except Exception as e:
            logger.error('[LOOKUP] Lỗi tìm tài khoản: %s', e)
    return None, None


def authenticate_user(account_number: str) -> Optional[Dict[str, Any]]:
    """
    Xác thực người dùng đăng nhập bằng số tài khoản.

    Args:
        account_number: Số tài khoản

    Returns:
        Thông tin user nếu đăng nhập thành công, None nếu thất bại
    """
    user, config = find_account_by_number(account_number)
    if not user or not config:
        return None

    return {
        'name': user['name'],
        'balance': user['balance'],
        'account_number': user['account_number'],
        'account_type': user.get('account_type'),
        'bank': config['database'],
    }


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
        conn = get_coordinator_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO transactions "
                "(tx_id, from_account, to_account, amount, status) "
                "VALUES (%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE "
                "from_account = VALUES(from_account), "
                "to_account = VALUES(to_account), "
                "amount = VALUES(amount), "
                "status = VALUES(status)",
                (
                    tx_id,
                    from_acc['account_number'],
                    to_acc['account_number'],
                    amount,
                    status,
                )
            )
        conn.close()
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
    seen = set()

    for config in ALL_DB_CONFIGS:
        db_name = config['database']
        bank_label = {
            'bank1': 'Ngân hàng 1',
            'bank2': 'Ngân hàng 2',
            'bank3': 'Ngân hàng 3',
        }.get(db_name, db_name)

        try:
            conn = get_connection(config)
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT name, balance, account_number, account_type, "
                    f"'{bank_label}' as bank FROM accounts"
                )
                rows = cursor.fetchall()
                for row in rows:
                    dedupe_key = (
                        str(row.get('account_number') or ''),
                    )
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    accounts.append(row)
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
            'account_number': acc['account_number'],
            'account_type': acc.get('account_type'),
        }
    return None
