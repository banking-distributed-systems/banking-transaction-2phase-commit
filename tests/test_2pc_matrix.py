"""
Comprehensive testcase matrix cho 2PC với schema mới.
"""

import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import two_phase_commit as tpc
from config import DB1_CONFIG


def _make_conn(fetchall_rows=None, execute_side_effect=None):
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


def _payload():
    return {
        'from_acc': {'name': 'User A', 'account_number': '102938475612'},
        'from_cfg': {'database': 'bank1'},
        'to_acc': {'name': 'User B', 'account_number': '203847569801'},
        'to_cfg': {'database': 'bank2'},
        'amount': 50000,
        'description': 'TC transfer',
    }


class Test2PCCoreCases:
    @patch('two_phase_commit.log_balance')
    @patch('account_service.save_transaction', return_value=True)
    @patch('two_phase_commit.log_phase')
    @patch('two_phase_commit.xa_prepare_participant', return_value=None)
    def test_tc01_happy_path_commit_success(self, _mock_prepare, mock_log_phase, _mock_save_tx, _mock_log_balance):
        payload = _payload()
        conn_a, _ = _make_conn()
        conn_b, _ = _make_conn()

        fixed_uuid = uuid.UUID('12345678-1234-5678-1234-567812345678')
        with patch('two_phase_commit.uuid.uuid4', return_value=fixed_uuid), patch(
            'two_phase_commit.get_connection', side_effect=[conn_a, conn_b]
        ):
            success, _message, tx_id, extra = tpc.execute_transfer(
                from_acc=payload['from_acc'],
                from_config=payload['from_cfg'],
                to_acc=payload['to_acc'],
                to_config=payload['to_cfg'],
                amount=payload['amount'],
                description=payload['description'],
            )

        assert success is True
        assert tx_id.startswith('VB')
        assert extra is None
        phases = [c.args[2] for c in mock_log_phase.call_args_list]
        assert phases == ['PREPARING', 'PREPARED', 'COMMITTING', 'COMMIT_A', 'COMMITTED']

    @patch('two_phase_commit.log_phase')
    @patch('two_phase_commit.rollback_xa_all')
    def test_tc02_prepare_fail_bank_a(self, mock_rollback_all, _mock_log_phase):
        payload = _payload()

        def prepare_side_effect(_cfg, _xid, _account_number, _amount, is_debit):
            if is_debit:
                raise Exception('Bank A insufficient funds')

        with patch('two_phase_commit.xa_prepare_participant', side_effect=prepare_side_effect):
            success, message, _tx_id, _extra = tpc.execute_transfer(
                from_acc=payload['from_acc'],
                from_config=payload['from_cfg'],
                to_acc=payload['to_acc'],
                to_config=payload['to_cfg'],
                amount=payload['amount'],
                description=payload['description'],
            )
        assert success is False
        assert 'Phase 1' in message
        assert mock_rollback_all.called

    @patch('two_phase_commit.log_balance')
    @patch('two_phase_commit.log_phase')
    @patch('two_phase_commit.xa_prepare_participant', return_value=None)
    @patch('two_phase_commit.xa_rollback')
    @patch('two_phase_commit.do_compensation', return_value=True)
    def test_tc04_partial_commit_b_fail_then_compensate(
        self,
        mock_compensate,
        mock_xa_rollback,
        _mock_prepare,
        _mock_log_phase,
        _mock_log_balance,
    ):
        payload = _payload()
        conn_a, _ = _make_conn()
        conn_b, _ = _make_conn(execute_side_effect=Exception('Bank B commit failed'))

        with patch('two_phase_commit.get_connection', side_effect=[conn_a, conn_b]):
            success, _message, _tx_id, extra = tpc.execute_transfer(
                from_acc=payload['from_acc'],
                from_config=payload['from_cfg'],
                to_acc=payload['to_acc'],
                to_config=payload['to_cfg'],
                amount=payload['amount'],
                description=payload['description'],
            )
        assert success is False
        assert extra['partial_failure'] is True
        assert extra['compensation'] is True
        assert mock_compensate.called
        mock_xa_rollback.assert_called_once()

    def test_log_phase_writes_extended_transaction_log_schema(self):
        participant_conn, participant_cursor = _make_conn()
        coordinator_conn, _ = _make_conn()
        table_schema = {
            'tx_id': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'xid': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'phase': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'amount': {'data_type': 'decimal', 'is_nullable': True, 'default': None, 'extra': ''},
            'from_account_number': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'to_account_number': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'from_name': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'to_name': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'description': {'data_type': 'varchar', 'is_nullable': True, 'default': '', 'extra': ''},
            'status': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'created_at': {'data_type': 'datetime', 'is_nullable': True, 'default': 'CURRENT_TIMESTAMP', 'extra': ''},
        }

        with patch('two_phase_commit.get_coordinator_conn', return_value=coordinator_conn), patch(
            'two_phase_commit.get_connection', return_value=participant_conn
        ), patch('two_phase_commit._get_transaction_log_schema', return_value=table_schema):
            tpc.log_phase(
                tx_id='VBEXTENDED01',
                xid='xid-extended-01',
                phase='ABORTED',
                from_acc={'name': 'User A', 'account_number': '102938475612'},
                to_acc={'name': 'User B', 'account_number': '203847569801'},
                from_config={'database': 'bank1'},
                to_config={'database': 'bank1'},
                amount=50000,
                description='extended-schema',
            )

        participant_sql, participant_params = participant_cursor.execute.call_args.args
        assert 'from_account_number' in participant_sql
        assert 'to_account_number' in participant_sql
        assert 'from_name' in participant_sql
        assert 'to_name' in participant_sql
        assert 'status' in participant_sql
        assert '102938475612' in participant_params
        assert '203847569801' in participant_params
        assert 'User A' in participant_params
        assert 'User B' in participant_params
        assert 'FAILED' in participant_params


class Test2PCRecoveryCases:
    def test_tc05_coordinator_crash_after_commit_a_recover_commit_b(self):
        xid = 'XID05'
        cfg_a = {'database': 'bank1'}
        cfg_b = {'database': 'bank2'}

        conn_a, _ = _make_conn(fetchall_rows=[])
        conn_b, _ = _make_conn(fetchall_rows=[(0, 0, 0, xid)])
        coordinator_conn, _ = _make_conn(fetchall_rows=[{
            'tx_id': 'VBXID05',
            'from_account': '102938475612',
            'to_account': '203847569801',
            'amount': 50000,
            'status': 'COMMIT_A',
        }])
        bank_log_a, _ = _make_conn(fetchall_rows=[{
            'tx_id': 'VBXID05',
            'xid': xid,
            'phase': 'COMMIT_A',
            'amount': 50000,
        }])
        bank_log_b, _ = _make_conn(fetchall_rows=[])

        def fake_get_connection(cfg):
            if cfg.get('database') == 'bank1':
                return bank_log_a if cfg.get('autocommit') else conn_a
            if cfg.get('database') == 'bank2':
                # conn_b has fetchall_rows=[(0,0,0,xid)] needed for XA RECOVER
                return conn_b
            return conn_b

        schema = {
            'tx_id': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'xid': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'phase': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'amount': {'data_type': 'decimal', 'is_nullable': True, 'default': None, 'extra': ''},
        }

        with patch.object(tpc, 'ALL_DB_CONFIGS', [cfg_a, cfg_b]), patch(
            'two_phase_commit.get_connection', side_effect=fake_get_connection
        ), patch('two_phase_commit.get_coordinator_conn', return_value=coordinator_conn), patch(
            'two_phase_commit.xa_commit', return_value=True
        ) as mock_commit, patch('two_phase_commit.log_phase'), patch(
            'two_phase_commit._get_transaction_log_schema', return_value=schema
        ):
            recovered = tpc.recover_in_doubt_transactions()

        assert recovered[0]['action'] == 'COMMIT_B_COMPLETED'
        mock_commit.assert_called_once_with(cfg_b, xid)

    def test_tc06_preparing_state_recover_abort(self):
        xid = 'XID06'
        cfg_a = {'database': 'bank1'}
        bank_conn, _ = _make_conn(fetchall_rows=[])
        bank_log_conn, _ = _make_conn(fetchall_rows=[{
            'tx_id': 'VBXID06',
            'xid': xid,
            'phase': 'PREPARING',
            'amount': 50000,
        }])
        coordinator_conn, _ = _make_conn(fetchall_rows=[{
            'tx_id': 'VBXID06',
            'from_account': '102938475612',
            'to_account': '203847569801',
            'amount': 50000,
            'status': 'PREPARING',
        }])

        schema = {
            'tx_id': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'xid': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'phase': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'amount': {'data_type': 'decimal', 'is_nullable': True, 'default': None, 'extra': ''},
        }

        with patch.object(tpc, 'ALL_DB_CONFIGS', [cfg_a]), patch(
            'two_phase_commit.get_connection', side_effect=[bank_conn, bank_log_conn]
        ), patch('two_phase_commit.get_coordinator_conn', return_value=coordinator_conn), patch(
            'two_phase_commit.rollback_xa_all'
        ) as mock_rollback, patch('two_phase_commit.log_phase'), patch(
            'two_phase_commit._get_transaction_log_schema', return_value=schema
        ):
            recovered = tpc.recover_in_doubt_transactions()

        assert recovered[0]['action'] == 'ABORTED'
        assert mock_rollback.called

    def test_recovery_uses_participant_from_account_when_coordinator_missing(self):
        xid = 'XID-COMMIT-A'
        cfg_a = {'database': 'bank1'}
        xa_recover_conn, _ = _make_conn(fetchall_rows=[])
        participant_log_conn, _ = _make_conn(fetchall_rows=[{
            'tx_id': 'VBPARTIAL01',
            'xid': xid,
            'phase': 'COMMIT_A',
            'amount': 10000,
            'from_account': '102938475612',
            'to_account': '203847569801',
        }])
        coordinator_conn, _ = _make_conn(fetchall_rows=[])

        schema = {
            'tx_id': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'xid': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'phase': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'amount': {'data_type': 'decimal', 'is_nullable': True, 'default': None, 'extra': ''},
            'from_account': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'to_account': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
        }

        with patch.object(tpc, 'ALL_DB_CONFIGS', [cfg_a]), patch(
            'two_phase_commit.get_connection', side_effect=[xa_recover_conn, participant_log_conn]
        ), patch('two_phase_commit.get_coordinator_conn', return_value=coordinator_conn), patch(
            'two_phase_commit._get_transaction_log_schema', return_value=schema
        ), patch('two_phase_commit.do_compensation', return_value=False) as mock_comp:
            recovered = tpc.recover_in_doubt_transactions()

        assert recovered[0]['action'] == 'COMPENSATION_FAILED'
        assert mock_comp.call_args.args[2] == '102938475612'

    def test_recovery_skips_when_coordinator_already_compensated(self):
        xid = 'XID-SKIP-COMP'
        cfg_a = {'database': 'bank1'}
        xa_recover_conn, _ = _make_conn(fetchall_rows=[])
        participant_log_conn, _ = _make_conn(fetchall_rows=[{
            'tx_id': 'VBSKIP0001',
            'xid': xid,
            'phase': 'COMMIT_A',
            'amount': 10000,
            'from_account': None,
            'to_account': None,
        }])
        coordinator_conn, coordinator_cursor = _make_conn(fetchall_rows=[{
            'tx_id': 'VBSKIP0001',
            'from_account': '102938475612',
            'to_account': '203847569801',
            'amount': 10000,
            'status': 'COMPENSATED',
        }])

        schema = {
            'tx_id': {'data_type': 'varchar', 'is_nullable': False, 'default': None, 'extra': ''},
            'xid': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'phase': {'data_type': 'varchar', 'is_nullable': True, 'default': None, 'extra': ''},
            'amount': {'data_type': 'decimal', 'is_nullable': True, 'default': None, 'extra': ''},
        }

        with patch.object(tpc, 'ALL_DB_CONFIGS', [cfg_a]), patch(
            'two_phase_commit.get_connection', side_effect=[xa_recover_conn, participant_log_conn]
        ), patch('two_phase_commit.get_coordinator_conn', return_value=coordinator_conn), patch(
            'two_phase_commit._get_transaction_log_schema', return_value=schema
        ), patch('two_phase_commit.do_compensation') as mock_comp:
            recovered = tpc.recover_in_doubt_transactions()

        assert recovered == []
        assert not mock_comp.called
        # Đảm bảo recovery có chạy query đối chiếu theo tx_id.
        assert coordinator_cursor.execute.call_count >= 2


class Test2PCIdempotencyAndConcurrency:
    def test_tc09_commit_sent_multiple_times_idempotent(self):
        conn_ok, _ = _make_conn()
        conn_fail, _ = _make_conn(execute_side_effect=Exception('XAER_NOTA'))
        with patch('two_phase_commit.get_connection', side_effect=[conn_ok, conn_fail]):
            assert tpc.xa_commit(DB1_CONFIG, 'XID09') is True
            assert tpc.xa_commit(DB1_CONFIG, 'XID09') is False

    @patch('account_service.save_transaction', return_value=True)
    @patch('two_phase_commit.log_phase')
    @patch('two_phase_commit.xa_prepare_participant', return_value=None)
    def test_tc11_concurrent_transfers_do_not_crash(self, _mock_prepare, _mock_log_phase, _mock_save_tx):
        payload = _payload()

        def conn_factory(_cfg):
            conn, _ = _make_conn()
            return conn

        uuid_values = [
            uuid.UUID('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
            uuid.UUID('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'),
        ]

        def run_once():
            return tpc.execute_transfer(
                from_acc=payload['from_acc'],
                from_config=payload['from_cfg'],
                to_acc=payload['to_acc'],
                to_config=payload['to_cfg'],
                amount=payload['amount'],
                description=payload['description'],
            )

        with patch('two_phase_commit.get_connection', side_effect=conn_factory), patch(
            'two_phase_commit.uuid.uuid4', side_effect=uuid_values
        ):
            with ThreadPoolExecutor(max_workers=2) as ex:
                results = list(ex.map(lambda _x: run_once(), [1, 2]))

        assert all(item[0] is True for item in results)
        assert results[0][2] != results[1][2]


class TestBusinessAndAuditCases:
    def test_tc12_transfer_reject_zero_or_negative_amount(self, client):
        for amount in (0, -1):
            response = client.post('/api/transfer', json={
                'from_account_number': '102938475612',
                'to_account_number': '203847569801',
                'amount': amount,
            })
            assert response.status_code == 400

    @patch('routes.recovery.recover_in_doubt_transactions')
    def test_tc16_recover_endpoint_returns_recovery_from_log(self, mock_recover, client):
        mock_recover.return_value = [{'tx_id': 'VB123', 'xid': 'XID16', 'action': 'COMMITTED'}]
        response = client.post('/api/recover')
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 1
        assert data['recovered'][0]['action'] == 'COMMITTED'
