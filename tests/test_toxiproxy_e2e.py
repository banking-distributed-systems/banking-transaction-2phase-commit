"""
E2E tests via Toxiproxy (localhost:8666).

These tests are opt-in and only run when RUN_TOXIPROXY_E2E=1.
"""

import json
import os
import time
import uuid
from urllib import error, request

import pytest

TOXIPROXY_API = "http://localhost:8474"
PROXY_NAME = "vbank_api"
API_PROXY = "http://localhost:8666/api"
API_DIRECT = "http://localhost:5000/api"


def _request_json(url, method="GET", payload=None, headers=None, timeout=8):
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")

    req = request.Request(url=url, data=data, headers=req_headers, method=method)

    try:
        with request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw) if raw else {}
            return res.getcode(), parsed, raw
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed, raw
    except error.URLError as exc:
        return 0, {"error": str(exc)}, ""


def _proxy_admin(path, method="GET", payload=None, timeout=8):
    headers = {"User-Agent": "curl"}
    return _request_json(
        url=f"{TOXIPROXY_API}{path}",
        method=method,
        payload=payload,
        headers=headers,
        timeout=timeout,
    )


def _clear_toxics():
    status, payload, _raw = _proxy_admin(f"/proxies/{PROXY_NAME}")
    if status != 200 or not isinstance(payload, dict):
        return

    for toxic in payload.get("toxics", []):
        toxic_name = toxic.get("name")
        if not toxic_name:
            continue
        _proxy_admin(f"/proxies/{PROXY_NAME}/toxics/{toxic_name}", method="DELETE")


@pytest.fixture(scope="module", autouse=True)
def require_e2e_env():
    if os.getenv("RUN_TOXIPROXY_E2E") != "1":
        pytest.skip("Set RUN_TOXIPROXY_E2E=1 to run Toxiproxy E2E tests")

    status_direct, _payload_direct, _ = _request_json(f"{API_DIRECT}/health", timeout=10)
    if status_direct != 200:
        pytest.skip("Backend API localhost:5000 is not ready")

    status_proxy, _payload_proxy, _ = _request_json(f"{API_PROXY}/health", timeout=10)
    if status_proxy != 200:
        pytest.skip("Proxy API localhost:8666 is not ready")

    yield
    _clear_toxics()


@pytest.fixture(autouse=True)
def cleanup_toxics_each_test():
    _clear_toxics()
    yield
    _clear_toxics()


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.slow
def test_proxy_is_registered_and_enabled():
    status, payload, _ = _proxy_admin("/proxies")
    assert status == 200
    assert PROXY_NAME in payload

    proxy_info = payload[PROXY_NAME]
    assert proxy_info.get("enabled") is True
    assert str(proxy_info.get("upstream", "")).endswith(":5000")


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.slow
def test_latency_toxic_affects_proxy_response_time():
    toxic_name = f"latency_{int(time.time())}"
    status, _payload, _ = _proxy_admin(
        f"/proxies/{PROXY_NAME}/toxics",
        method="POST",
        payload={
            "name": toxic_name,
            "type": "latency",
            "stream": "downstream",
            "attributes": {"latency": 400},
        },
    )
    assert status in (200, 201)

    started = time.time()
    health_status, health_payload, _ = _request_json(f"{API_PROXY}/health", timeout=12)
    elapsed = time.time() - started

    assert health_status == 200
    assert health_payload.get("status") == "ok"
    assert elapsed >= 0.35


@pytest.mark.e2e
@pytest.mark.integration
@pytest.mark.slow
def test_tc14_idempotency_double_submit_via_proxy():
    idem_key = f"E2E-TC14-{uuid.uuid4().hex[:10].upper()}"
    body = {
        "from_account_number": "102938475612",
        "to_account_number": "203847569801",
        "amount": 1,
        "description": "TC14 E2E double submit",
    }
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": idem_key,
    }

    status_1, payload_1, _ = _request_json(
        f"{API_PROXY}/transfer",
        method="POST",
        payload=body,
        headers=headers,
        timeout=20,
    )
    status_2, payload_2, _ = _request_json(
        f"{API_PROXY}/transfer",
        method="POST",
        payload=body,
        headers=headers,
        timeout=20,
    )

    assert status_1 == 200
    assert status_2 == 200
    assert payload_1.get("status") == "success"
    assert payload_2.get("idempotent_replay") is True
    assert payload_2.get("tx_id") == payload_1.get("tx_id")
