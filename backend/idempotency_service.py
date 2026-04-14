"""
Idempotency service cho API transfer.
"""

import json
import hashlib
from typing import Any, Dict, Optional

import pymysql

from database import get_log_conn
from logger import get_logger

logger = get_logger(__name__)


def build_request_hash(payload: Dict[str, Any]) -> str:
    """Tạo hash ổn định từ payload để so sánh request duplicate."""
    normalized = {
        "from_account_number": str(payload.get("from_account_number") or "").replace(" ", ""),
        "to_account_number": str(payload.get("to_account_number") or "").replace(" ", ""),
        "amount": str(payload.get("amount") or ""),
        "description": str(payload.get("description") or ""),
    }
    raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_idempotency_record(idem_key: str) -> Optional[Dict[str, Any]]:
    conn = None
    try:
        conn = get_log_conn()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT idem_key, request_hash, status, tx_id, http_status, response_json "
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


def create_processing_record(idem_key: str, request_hash: str) -> bool:
    conn = None
    try:
        conn = get_log_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO idempotency_keys (idem_key, request_hash, status) VALUES (%s, %s, 'PROCESSING')",
                (idem_key, request_hash),
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
    http_status: int,
    payload: Dict[str, Any],
    success: bool,
) -> None:
    conn = None
    try:
        conn = get_log_conn()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE idempotency_keys "
                "SET status = %s, tx_id = %s, http_status = %s, response_json = %s "
                "WHERE idem_key = %s",
                (
                    "COMPLETED" if success else "FAILED",
                    tx_id,
                    int(http_status),
                    json.dumps(payload, ensure_ascii=False),
                    idem_key,
                ),
            )
    except Exception as e:
        logger.error("[IDEMPOTENCY] Lỗi finalize key %s: %s", idem_key, e)
    finally:
        if conn:
            conn.close()


def parse_stored_response(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = record.get("response_json")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return None
    except Exception:
        return None
