"""
Integration/unit tests cho transfer API theo contract mới.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestTransferAPI:
    def test_transfer_endpoint_exists(self, client):
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 50000,
            'description': 'Test',
        })
        assert response.status_code in [200, 400, 408, 500]

    def test_transfer_requires_amount(self, client):
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
        })
        assert response.status_code == 400

    def test_transfer_rejects_negative_amount(self, client):
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': -1,
        })
        assert response.status_code == 400

    @patch('routes.transfer.find_account_by_number')
    @patch('routes.transfer.execute_transfer')
    def test_transfer_success(self, mock_execute, mock_find, client):
        mock_find.side_effect = [
            ({'name': 'A', 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'name': 'B', 'account_number': '203847569801'}, {'database': 'bank2'}),
        ]
        mock_execute.return_value = (True, 'Success', 'VB12345678', None)

        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 50000,
            'description': 'Test transfer',
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['tx_id'] == 'VB12345678'

    @patch('routes.transfer.find_account_by_number')
    def test_transfer_same_account_rejected(self, mock_find, client):
        mock_find.side_effect = [
            ({'name': 'A', 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'name': 'A', 'account_number': '102938475612'}, {'database': 'bank1'}),
        ]
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '102938475612',
            'amount': 50000,
        })
        assert response.status_code == 400

    @patch('routes.transfer.find_account_by_number', return_value=(None, None))
    def test_transfer_source_not_found(self, _mock_find, client):
        response = client.post('/api/transfer', json={
            'from_account_number': '999999999999',
            'to_account_number': '203847569801',
            'amount': 50000,
        })
        assert response.status_code == 400


class TestTransferIdempotency:
    @patch('routes.transfer.get_idempotency_record')
    def test_transfer_replay_returns_existing_tx(self, mock_get_record, client):
        mock_get_record.return_value = {
            'idem_key': 'IDEMP-123',
            'status': 'COMPLETED',
            'tx_id': 'VB12345678',
        }
        response = client.post(
            '/api/transfer',
            json={
                'from_account_number': '102938475612',
                'to_account_number': '203847569801',
                'amount': 10000,
                'description': 'idem replay',
            },
            headers={'Idempotency-Key': 'IDEMP-123'},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['idempotent_replay'] is True
        assert data['tx_id'] == 'VB12345678'

    @patch('routes.transfer.finalize_record')
    @patch('routes.transfer.execute_transfer')
    @patch('routes.transfer.create_processing_record', return_value=True)
    @patch('routes.transfer.get_idempotency_record', return_value=None)
    @patch('routes.transfer.find_account_by_number')
    def test_transfer_finalize_called(
        self,
        mock_find,
        _mock_get_record,
        _mock_create,
        mock_execute,
        mock_finalize,
        client,
    ):
        mock_find.side_effect = [
            ({'name': 'A', 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'name': 'B', 'account_number': '203847569801'}, {'database': 'bank2'}),
        ]
        mock_execute.return_value = (True, 'Success', 'VB99999999', None)

        response = client.post(
            '/api/transfer',
            json={
                'from_account_number': '102938475612',
                'to_account_number': '203847569801',
                'amount': 10000,
                'description': 'idem normal',
            },
            headers={'Idempotency-Key': 'IDEMP-NEW'},
        )

        assert response.status_code == 200
        mock_finalize.assert_called_once()


class TestTransferStatusAndRecent:
    @patch('routes.transfer._get_transaction_status', return_value=None)
    def test_transfer_status_not_found(self, _mock_status, client):
        response = client.get('/api/transfer/status/VB_NOT_FOUND')
        assert response.status_code == 404

    @patch('routes.transfer._get_transaction_status')
    def test_transfer_status_success(self, mock_status, client):
        mock_status.return_value = {
            'tx_id': 'VB123',
            'xid': 'xid123',
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 10000,
            'phase': 'COMMITTED',
            'phase_label': 'Phase 2',
            'business_status': 'COMMITTED',
            'message': 'Giao dịch đã hoàn tất thành công.',
            'created_at': '2026-04-14 20:00:00',
            'updated_at': '2026-04-14 20:00:10',
        }
        response = client.get('/api/transfer/status/VB123')
        assert response.status_code == 200
        assert response.get_json()['data']['phase'] == 'COMMITTED'

    @patch('routes.transfer._get_recent_transactions', return_value=[])
    def test_transfer_recent_success_empty(self, _mock_recent, client):
        response = client.get('/api/transfer/recent')
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 0

    @patch('routes.transfer._get_recent_transactions')
    def test_transfer_recent_returns_items(self, mock_recent, client):
        mock_recent.return_value = [{
            'tx_id': 'VB100',
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 10000.0,
            'phase': 'COMMITTING',
            'phase_label': 'Phase 2',
            'message': 'Coordinator đang gửi commit.',
            'updated_at': '2026-04-14 22:00:00',
        }]
        response = client.get('/api/transfer/recent?limit=5')
        assert response.status_code == 200
        data = response.get_json()
        assert data['count'] == 1
        mock_recent.assert_called_once_with(5)
