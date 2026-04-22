"""
Database connection và helper functions
"""

import pymysql
from typing import Optional, Dict, Any, List
from config import ALL_DB_CONFIGS, COORDINATOR_DB_CONFIG
from logger import get_logger

logger = get_logger(__name__)


def get_connection(config: Dict[str, Any] = None, **kwargs) -> pymysql.Connection:
    """
    Tạo kết nối database mới

    Args:
        config: Database configuration dictionary

    Returns:
        PyMySQL connection
    """
    final_config = dict(config or {})
    if kwargs:
        final_config.update(kwargs)
    return pymysql.connect(**final_config)


def get_coordinator_conn() -> pymysql.Connection:
    """
    Kết nối autocommit tới database coordinator.

    Returns:
        PyMySQL connection với autocommit=True
    """
    return get_connection(**{**COORDINATOR_DB_CONFIG, 'autocommit': True})


def execute_query(
    config: Dict[str, Any],
    sql: str,
    params: tuple = None,
    fetch_one: bool = False,
    fetch_all: bool = False,
    dict_cursor: bool = True
) -> Optional[Any]:
    """
    Thực thi một câu query đơn giản

    Args:
        config: Database configuration
        sql: SQL query
        params: Parameters cho query
        fetch_one: Lấy một record
        fetch_all: Lấy tất cả records
        dict_cursor: Sử dụng DictCursor

    Returns:
        Kết quả query hoặc None nếu lỗi
    """
    conn = None
    try:
        conn = get_connection(config)
        cursor_class = pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor
        with conn.cursor(cursor_class) as cur:
            cur.execute(sql, params)
            if fetch_one:
                return cur.fetchone()
            elif fetch_all:
                return cur.fetchall()
            return cur.rowcount
    except Exception as e:
        logger.error('[DB] Lỗi thực thi query: %s', e)
        return None
    finally:
        if conn:
            conn.close()


def execute_query_autocommit(
    config: Dict[str, Any],
    sql: str,
    params: tuple = None,
    fetch_one: bool = False,
    fetch_all: bool = False
) -> Optional[Any]:
    """
    Thực thi query với autocommit=True

    Args:
        config: Database configuration
        sql: SQL query
        params: Parameters cho query
        fetch_one: Lấy một record
        fetch_all: Lấy tất cả records

    Returns:
        Kết quả query hoặc None nếu lỗi
    """
    conn = None
    try:
        conn = get_connection(**{**config, 'autocommit': True})
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params)
            if fetch_one:
                return cur.fetchone()
            elif fetch_all:
                return cur.fetchall()
            return cur.rowcount
    except Exception as e:
        logger.error('[DB] Lỗi thực thi query (autocommit): %s', e)
        return None
    finally:
        if conn:
            conn.close()


def get_all_accounts() -> List[Dict[str, Any]]:
    """
    Lấy tất cả tài khoản từ cả hai database

    Returns:
        List of accounts
    """
    accounts = []

    for config in ALL_DB_CONFIGS:
        db_name = config['database']
        try:
            conn = get_connection(config)
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT name, balance, account_number, account_type, "
                    f"'{db_name}' as bank FROM accounts"
                )
                accounts.extend(cursor.fetchall())
            conn.close()
        except Exception as e:
            logger.error('[ACCOUNTS] Lỗi kết nối %s: %s', db_name, e)

    return accounts


def ensure_runtime_schema() -> None:
    """Khởi tạo các bảng/phần schema cần cho runtime nếu chưa tồn tại."""
    coordinator_conn = None
    try:
        coordinator_conn = get_coordinator_conn()
        with coordinator_conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS transactions ("
                "tx_id VARCHAR(30) PRIMARY KEY,"
                "from_account VARCHAR(20),"
                "to_account VARCHAR(20),"
                "amount DECIMAL(15,2),"
                "status VARCHAR(20),"
                "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                ") ENGINE=InnoDB"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS idempotency_keys ("
                "idem_key VARCHAR(128) PRIMARY KEY,"
                "status VARCHAR(20),"
                "tx_id VARCHAR(30)"
                ") ENGINE=InnoDB"
            )
        for config in ALL_DB_CONFIGS:
            bank_conn = None
            try:
                bank_conn = get_connection({**config, 'autocommit': True})
                with bank_conn.cursor() as cur:
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS transaction_log ("
                        "tx_id VARCHAR(30) PRIMARY KEY,"
                        "xid VARCHAR(64),"
                        "phase VARCHAR(20),"
                        "amount DECIMAL(15,2),"
                        "created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
                        ") ENGINE=InnoDB"
                    )
            finally:
                if bank_conn:
                    bank_conn.close()
    except Exception as e:
        logger.warning('[DB] Không thể ensure runtime schema: %s', e)
    finally:
        if coordinator_conn:
            coordinator_conn.close()
