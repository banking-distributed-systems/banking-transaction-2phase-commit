"""
Comprehensive testcase matrix for 2PC scenarios (TC01-TC16).

These tests focus on deterministic unit/integration behavior using mocks,
so they can run in CI without requiring real multi-DB crash orchestration.
"""

import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import two_phase_commit as tpc
from config import DB1_CONFIG, DB2_CONFIG


def _make_conn(fetchall_rows=None, execute_side_effect=None):
    """Create a lightweight mocked DB connection with context-manager cursor."""
    cursor = MagicMock()
    if fetchall_rows is not None:
        cursor.fetchall.return_value = fetchall_rows
    if execute_side_effect is not None:
        cursor.execute.side_effect = execute_side_effect

    conn = MagicMock()
    ctx = MagicMock()
    ctx.__enter__.return_value = cursor
    ctx.__exit__.return_value = False
    conn.cursor.return_value = ctx
    return conn, cursor


@pytest.fixture
def transfer_payload():
    return {
        "from_acc": {
            "id": 1,
            "name": "User A",
            "account_number": "102938475612",
        },
        "from_cfg": {"database": "bank1"},
        "to_acc": {
            "id": 2,
            "name": "User B",
            "account_number": "203847569801",
        },
        "to_cfg": {"database": "bank2"},
        "amount": 50000,
        "description": "TC transfer",
    }


class Test2PCCoreCases:
    """TC01-TC04 core 2PC execution cases."""

    @patch("account_service.save_transaction", return_value=True)
    @patch("two_phase_commit.log_phase")
    @patch("two_phase_commit.xa_prepare_participant", return_value=None)
    def test_tc01_happy_path_commit_success(
        self,
        _mock_prepare,
        mock_log_phase,
        _mock_save_tx,
        transfer_payload,
    ):
        """TC01: A/B prepare YES, coordinator commits both."""
        conn_a, _ = _make_conn()
        conn_b, _ = _make_conn()

        fixed_uuid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        with patch("two_phase_commit.uuid.uuid4", return_value=fixed_uuid), patch(
            "two_phase_commit.get_connection", side_effect=[conn_a, conn_b]
        ):
            success, message, tx_id, extra = tpc.execute_transfer(
                from_acc=transfer_payload["from_acc"],
                from_config=transfer_payload["from_cfg"],
                to_acc=transfer_payload["to_acc"],
                to_config=transfer_payload["to_cfg"],
                amount=transfer_payload["amount"],
                description=transfer_payload["description"],
            )

        assert success is True
        assert tx_id.startswith("VB")
        assert "2-Phase Commit" in message
        assert extra is None

        phases = [c.args[2] for c in mock_log_phase.call_args_list]
        assert phases == ["PREPARING", "PREPARED", "COMMITTING", "COMMIT_A", "COMMITTED"]

    @patch("two_phase_commit.log_phase")
    @patch("two_phase_commit.rollback_xa_all")
    def test_tc02_prepare_fail_bank_a(self, mock_rollback_all, _mock_log_phase, transfer_payload):
        """TC02: Bank A fails in phase-1 (prepare)."""

        def prepare_side_effect(_cfg, _xid, _account_id, _amount, is_debit):
            if is_debit:
                raise Exception("Bank A insufficient funds")
            return None

        with patch("two_phase_commit.xa_prepare_participant", side_effect=prepare_side_effect):
            success, message, _tx_id, _extra = tpc.execute_transfer(
                from_acc=transfer_payload["from_acc"],
                from_config=transfer_payload["from_cfg"],
                to_acc=transfer_payload["to_acc"],
                to_config=transfer_payload["to_cfg"],
                amount=transfer_payload["amount"],
                description=transfer_payload["description"],
            )

        assert success is False
        assert "Phase 1" in message
        assert mock_rollback_all.called

    @patch("two_phase_commit.log_phase")
    @patch("two_phase_commit.rollback_xa_all")
    def test_tc03_prepare_fail_bank_b(self, mock_rollback_all, _mock_log_phase, transfer_payload):
        """TC03: Bank B fails in phase-1 (prepare)."""

        def prepare_side_effect(_cfg, _xid, _account_id, _amount, is_debit):
            if not is_debit:
                raise Exception("Bank B rejected transaction")
            return None

        with patch("two_phase_commit.xa_prepare_participant", side_effect=prepare_side_effect):
            success, message, _tx_id, _extra = tpc.execute_transfer(
                from_acc=transfer_payload["from_acc"],
                from_config=transfer_payload["from_cfg"],
                to_acc=transfer_payload["to_acc"],
                to_config=transfer_payload["to_cfg"],
                amount=transfer_payload["amount"],
                description=transfer_payload["description"],
            )

        assert success is False
        assert "Phase 1" in message
        assert mock_rollback_all.called

    @patch("two_phase_commit.log_phase")
    @patch("two_phase_commit.xa_prepare_participant", return_value=None)
    @patch("two_phase_commit.xa_rollback")
    @patch("two_phase_commit.do_compensation", return_value=True)
    def test_tc04_partial_commit_b_fail_then_compensate(
        self,
        mock_compensate,
        mock_xa_rollback,
        _mock_prepare,
        _mock_log_phase,
        transfer_payload,
    ):
        """TC04: Commit A success, commit B fails -> compensation."""
        conn_a, _ = _make_conn()
        conn_b, _ = _make_conn(execute_side_effect=Exception("Bank B commit failed"))

        with patch("two_phase_commit.get_connection", side_effect=[conn_a, conn_b]):
            success, message, _tx_id, extra = tpc.execute_transfer(
                from_acc=transfer_payload["from_acc"],
                from_config=transfer_payload["from_cfg"],
                to_acc=transfer_payload["to_acc"],
                to_config=transfer_payload["to_cfg"],
                amount=transfer_payload["amount"],
                description=transfer_payload["description"],
            )

        assert success is False
        assert extra is not None
        assert extra["partial_failure"] is True
        assert extra["compensation"] is True
        assert mock_compensate.called
        mock_xa_rollback.assert_called_once()
        assert "Kịch bản 4" in message


class Test2PCRecoveryCases:
    """TC05-TC08 + TC16 recovery-oriented cases."""

    def test_tc05_coordinator_crash_after_commit_a_recover_commit_b(self):
        """TC05: Recover path COMMIT_A -> complete Bank B commit."""
        xid = "XID05"
        log_entry = {
            "xid": xid,
            "tx_id": "VBXID05",
            "phase": "COMMIT_A",
            "from_account_number": "102938475612",
            "amount": 50000,
        }

        cfg_a = {"database": "bank1"}
        cfg_b = {"database": "bank2"}

        conn_a, _ = _make_conn(fetchall_rows=[])
        conn_b, _ = _make_conn(fetchall_rows=[(0, 0, 0, xid)])
        log_conn, log_cur = _make_conn(fetchall_rows=[log_entry])

        def fake_get_connection(cfg):
            return conn_a if cfg.get("database") == "bank1" else conn_b

        with patch.object(tpc, "ALL_DB_CONFIGS", [cfg_a, cfg_b]), patch(
            "two_phase_commit.get_connection", side_effect=fake_get_connection
        ), patch("two_phase_commit.get_log_conn", return_value=log_conn), patch(
            "two_phase_commit.xa_commit", return_value=True
        ) as mock_commit, patch("two_phase_commit.log_phase"):
            recovered = tpc.recover_in_doubt_transactions()

        assert recovered
        assert recovered[0]["action"] == "COMMIT_B_COMPLETED"
        mock_commit.assert_called_once_with(cfg_b, xid)
        assert log_cur.execute.called

    def test_tc06_coordinator_crash_before_commit_recover_abort(self):
        """TC06: PREPARING state should be aborted on recovery."""
        xid = "XID06"
        log_entry = {
            "xid": xid,
            "tx_id": "VBXID06",
            "phase": "PREPARING",
            "from_account_number": "102938475612",
            "amount": 50000,
        }

        cfg_a = {"database": "bank1"}
        cfg_b = {"database": "bank2"}
        conn_a, _ = _make_conn(fetchall_rows=[])
        conn_b, _ = _make_conn(fetchall_rows=[])
        log_conn, _ = _make_conn(fetchall_rows=[log_entry])

        def fake_get_connection(cfg):
            return conn_a if cfg.get("database") == "bank1" else conn_b

        with patch.object(tpc, "ALL_DB_CONFIGS", [cfg_a, cfg_b]), patch(
            "two_phase_commit.get_connection", side_effect=fake_get_connection
        ), patch("two_phase_commit.get_log_conn", return_value=log_conn), patch(
            "two_phase_commit.rollback_xa_all"
        ) as mock_rollback, patch("two_phase_commit.log_phase"):
            recovered = tpc.recover_in_doubt_transactions()

        assert recovered
        assert recovered[0]["action"] == "ABORTED"
        assert mock_rollback.called

    def test_tc07_participant_crash_after_prepare_recover_commit(self):
        """TC07: PREPARED state should continue commit on recovery."""
        xid = "XID07"
        log_entry = {
            "xid": xid,
            "tx_id": "VBXID07",
            "phase": "PREPARED",
            "from_account_number": "102938475612",
            "amount": 50000,
        }

        cfg_a = {"database": "bank1"}
        cfg_b = {"database": "bank2"}
        conn_a, _ = _make_conn(fetchall_rows=[(0, 0, 0, xid)])
        conn_b, _ = _make_conn(fetchall_rows=[(0, 0, 0, xid)])
        log_conn, _ = _make_conn(fetchall_rows=[log_entry])

        def fake_get_connection(cfg):
            return conn_a if cfg.get("database") == "bank1" else conn_b

        with patch.object(tpc, "ALL_DB_CONFIGS", [cfg_a, cfg_b]), patch(
            "two_phase_commit.get_connection", side_effect=fake_get_connection
        ), patch("two_phase_commit.get_log_conn", return_value=log_conn), patch(
            "two_phase_commit.xa_commit", return_value=True
        ) as mock_commit, patch("two_phase_commit.log_phase"):
            recovered = tpc.recover_in_doubt_transactions()

        assert recovered
        assert recovered[0]["action"] == "COMMITTED"
        assert mock_commit.call_count == 2

    def test_tc08_in_doubt_state_waiting_coordinator_then_recover(self):
        """TC08: COMMITTING state in-doubt is resolved by recovery coordinator."""
        xid = "XID08"
        log_entry = {
            "xid": xid,
            "tx_id": "VBXID08",
            "phase": "COMMITTING",
            "from_account_number": "102938475612",
            "amount": 50000,
        }

        cfg_a = {"database": "bank1"}
        conn_a, _ = _make_conn(fetchall_rows=[(0, 0, 0, xid)])
        log_conn, _ = _make_conn(fetchall_rows=[log_entry])

        with patch.object(tpc, "ALL_DB_CONFIGS", [cfg_a]), patch(
            "two_phase_commit.get_connection", return_value=conn_a
        ), patch("two_phase_commit.get_log_conn", return_value=log_conn), patch(
            "two_phase_commit.xa_commit", return_value=True
        ):
            recovered = tpc.recover_in_doubt_transactions()

        assert recovered
        assert recovered[0]["action"] == "COMMITTED"


class Test2PCIdempotencyAndConcurrency:
    """TC09-TC11 + TC14 behavior checks."""

    def test_tc09_commit_sent_multiple_times_idempotent(self):
        """TC09: Repeated commit should not crash coordinator logic."""
        conn_ok, _ = _make_conn()
        conn_fail, _ = _make_conn(execute_side_effect=Exception("XAER_NOTA"))

        with patch("two_phase_commit.get_connection", side_effect=[conn_ok, conn_fail]):
            first = tpc.xa_commit(DB1_CONFIG, "XID09")
            second = tpc.xa_commit(DB1_CONFIG, "XID09")

        assert first is True
        assert second is False

    def test_tc10_rollback_sent_multiple_times_idempotent(self):
        """TC10: Repeated rollback should not raise exceptions to caller."""
        conn_ok, _ = _make_conn()
        conn_fail, _ = _make_conn(execute_side_effect=Exception("XAER_NOTA"))

        with patch("two_phase_commit.get_connection", side_effect=[conn_ok, conn_fail]):
            tpc.xa_rollback(DB1_CONFIG, "XID10")
            tpc.xa_rollback(DB1_CONFIG, "XID10")

    @patch("account_service.save_transaction", return_value=True)
    @patch("two_phase_commit.log_phase")
    @patch("two_phase_commit.xa_prepare_participant", return_value=None)
    def test_tc11_concurrent_transfers_do_not_crash(
        self,
        _mock_prepare,
        _mock_log_phase,
        _mock_save_tx,
        transfer_payload,
    ):
        """TC11: Two concurrent transfers should complete without coordinator crash."""

        def conn_factory(_cfg):
            conn, _ = _make_conn()
            return conn

        uuid_values = [
            uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        ]

        def run_once():
            return tpc.execute_transfer(
                from_acc=transfer_payload["from_acc"],
                from_config=transfer_payload["from_cfg"],
                to_acc=transfer_payload["to_acc"],
                to_config=transfer_payload["to_cfg"],
                amount=transfer_payload["amount"],
                description=transfer_payload["description"],
            )

        with patch("two_phase_commit.get_connection", side_effect=conn_factory), patch(
            "two_phase_commit.uuid.uuid4", side_effect=uuid_values
        ):
            with ThreadPoolExecutor(max_workers=2) as ex:
                results = list(ex.map(lambda _x: run_once(), [1, 2]))

        assert all(r[0] is True for r in results)
        assert results[0][2] != results[1][2]

    @pytest.mark.xfail(reason="Idempotency key/dedupe for double-submit is not implemented yet")
    @patch("routes.transfer.find_account_by_number")
    @patch("routes.transfer.execute_transfer")
    def test_tc14_double_submit_should_process_once(
        self, mock_execute_transfer, mock_find_account, client
    ):
        """TC14: Desired behavior is one processing for double submit."""
        mock_find_account.side_effect = [
            ({"id": 1, "account_number": "102938475612"}, {"database": "bank1"}),
            ({"id": 2, "account_number": "203847569801"}, {"database": "bank2"}),
            ({"id": 1, "account_number": "102938475612"}, {"database": "bank1"}),
            ({"id": 2, "account_number": "203847569801"}, {"database": "bank2"}),
        ]
        mock_execute_transfer.return_value = (True, "ok", "VBIDEMPOTENT", None)

        payload = {
            "from_account_number": "102938475612",
            "to_account_number": "203847569801",
            "amount": 10000,
            "description": "double click",
        }

        client.post("/api/transfer", json=payload)
        client.post("/api/transfer", json=payload)

        assert mock_execute_transfer.call_count == 1


class TestBusinessAndAuditCases:
    """TC12-TC13 + TC15-TC16."""

    def test_tc12_transfer_reject_zero_or_negative_amount(self, client):
        """TC12: Amount <= 0 must be rejected."""
        payload_zero = {
            "from_account_number": "102938475612",
            "to_account_number": "203847569801",
            "amount": 0,
            "description": "invalid",
        }
        payload_negative = {
            "from_account_number": "102938475612",
            "to_account_number": "203847569801",
            "amount": -1,
            "description": "invalid",
        }

        r1 = client.post("/api/transfer", json=payload_zero)
        r2 = client.post("/api/transfer", json=payload_negative)

        assert r1.status_code == 400
        assert r2.status_code == 400

    @patch("routes.transfer.find_account_by_number")
    def test_tc13_transfer_reject_missing_account(self, mock_find_account, client):
        """TC13: Missing source account should return validation error."""
        mock_find_account.return_value = (None, None)

        response = client.post(
            "/api/transfer",
            json={
                "from_account_number": "999999999999",
                "to_account_number": "203847569801",
                "amount": 10000,
                "description": "missing source",
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"

    @patch("account_service.save_transaction", return_value=True)
    @patch("two_phase_commit.xa_prepare_participant", return_value=None)
    def test_tc15_transaction_logs_have_prepare_commit_rollback_markers(
        self, _mock_prepare, _mock_save_tx, transfer_payload
    ):
        """TC15: Verify phase logging contains critical audit milestones."""
        conn_a, _ = _make_conn()
        conn_b, _ = _make_conn()

        with patch("two_phase_commit.get_connection", side_effect=[conn_a, conn_b]), patch(
            "two_phase_commit.log_phase"
        ) as mock_log_phase:
            success, _msg, _txid, _extra = tpc.execute_transfer(
                from_acc=transfer_payload["from_acc"],
                from_config=transfer_payload["from_cfg"],
                to_acc=transfer_payload["to_acc"],
                to_config=transfer_payload["to_cfg"],
                amount=transfer_payload["amount"],
                description=transfer_payload["description"],
            )

        assert success is True
        phases = [c.args[2] for c in mock_log_phase.call_args_list]
        assert "PREPARING" in phases
        assert "COMMITTED" in phases

    @patch("routes.recovery.recover_in_doubt_transactions")
    def test_tc16_recover_endpoint_returns_recovery_from_log(self, mock_recover, client):
        """TC16: Recovery endpoint should return recovered transactions list."""
        mock_recover.return_value = [
            {"tx_id": "VB123", "xid": "XID16", "action": "COMMITTED"}
        ]

        response = client.post("/api/recover")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "success"
        assert data["count"] == 1
        assert data["recovered"][0]["action"] == "COMMITTED"
