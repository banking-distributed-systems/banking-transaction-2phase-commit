"""Basic frontend smoke checks for monitor and recovery UI wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_monitor_dom_elements_exist_in_index_html():
    html = _read_text(ROOT / "index.html")

    required_tokens = [
        'id="statusTxIdInput"',
        'id="statusTxResult"',
        'id="txRecentList"',
        'id="txAutoRefresh"',
        'onclick="lookupTransactionStatus()"',
        'onclick="runManualRecovery()"',
    ]

    for token in required_tokens:
        assert token in html


def test_monitor_functions_exist_in_frontend_js():
    js = _read_text(ROOT / "frontend" / "app.js")

    required_tokens = [
        'const API_URL = "http://localhost:8666/api";',
        "function fetchRecentTransactions",
        "function runManualRecovery",
        "function toggleTxAutoRefresh",
        "function lookupTransactionStatus",
        "function showDashboard",
    ]

    for token in required_tokens:
        assert token in js
