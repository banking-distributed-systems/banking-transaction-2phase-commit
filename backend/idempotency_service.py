"""
Idempotency service cho API transfer.
"""

from typing import Dict, Optional
from typing import Any
import pymysql

from database import get_coordinator_conn
from logger import get_logger

logger = get_logger(__name__)


def get_idempotency_record(idem_key: str) -> Optional[Dict[str, Any]]:
    conn = None
    try:
        conn = get_coordinator_conn()
        # Read idempotency state for the given key (single-row lookup).
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT idem_key, status, tx_id "
                "FROM idempotency_keys WHERE idem_key = %s",
                (idem_key,),
            )
            return cur.fetchone()
    except Exception as e:
        logger.error("[IDEMPOTENCY] Lỗi đọc key %s: %s", idem_key, e)
        return None
    finally:
        if conn:
            conn.close()


def create_processing_record(idem_key: str) -> bool:
    conn = None
    try:
        conn = get_coordinator_conn()
        # Insert a fresh key in PROCESSING; unique constraint prevents duplicates.
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO idempotency_keys (idem_key, status, tx_id) VALUES (%s, 'PROCESSING', NULL)",
                (idem_key,),
            )
        return True
    except pymysql.IntegrityError:
        return False
    except Exception as e:
        logger.error("[IDEMPOTENCY] Lỗi tạo key %s: %s", idem_key, e)
        return False
    finally:
        if conn:
            conn.close()


def finalize_record(
    idem_key: str,
    tx_id: Optional[str],
    success: bool,
) -> None:
    conn = None
    try:
        conn = get_coordinator_conn()
        # Finalize outcome and persist the transaction id for replay handling.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE idempotency_keys "
                "SET status = %s, tx_id = %s "
                "WHERE idem_key = %s",
                (
                    "COMPLETED" if success else "FAILED",
                    tx_id,
                    idem_key,
                ),
            )
    except Exception as e:
        logger.error("[IDEMPOTENCY] Lỗi finalize key %s: %s", idem_key, e)
    finally:
        if conn:
            conn.close()


def parse_stored_response(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Placeholder for parsing a stored response payload (not yet implemented).
    return None
