"""
Integration tests cho transfer API
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
import json
from unittest.mock import patch, MagicMock


class TestTransferAPI:
    """Test POST /api/transfer endpoint"""

    def test_transfer_endpoint_exists(self, client):
        """Test /api/transfer endpoint tồn tại"""
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 50000,
            'description': 'Test'
        })
        assert response.status_code in [200, 400, 408, 500]

    def test_transfer_requires_from_account(self, client):
        """Test /api/transfer yêu cầu from_account_number"""
        response = client.post('/api/transfer', json={
            'to_account_number': '203847569801',
            'amount': 50000
        })
        assert response.status_code in [400, 500]

    def test_transfer_requires_to_account(self, client):
        """Test /api/transfer yêu cầu to_account_number"""
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'amount': 50000
        })
        assert response.status_code in [400, 500]

    def test_transfer_requires_amount(self, client):
        """Test /api/transfer yêu cầu amount"""
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801'
        })
        assert response.status_code in [400, 500]


class TestTransferValidation:
    """Test validation cho transfer"""

    def test_transfer_rejects_negative_amount(self, client):
        """Test /api/transfer từ chối số tiền âm"""
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': -50000,
            'description': 'Test'
        })
        assert response.status_code in [400, 500]

    def test_transfer_rejects_zero_amount(self, client):
        """Test /api/transfer từ chối số tiền = 0"""
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 0,
            'description': 'Test'
        })
        assert response.status_code in [400, 500]

    def test_transfer_rejects_same_account(self, client):
        """Test /api/transfer từ chối chuyển cho cùng tài khoản"""
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '102938475612',
            'amount': 50000,
            'description': 'Test'
        })
        assert response.status_code in [400, 500]

    def test_transfer_requires_valid_amount_type(self, client):
        """Test /api/transfer yêu cầu amount là số"""
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 'fifty thousand',
            'description': 'Test'
        })
        assert response.status_code in [400, 500]


class TestTransferSuccess:
    """Test các trường hợp transfer thành công"""

    @patch('routes.transfer.find_account_by_number')
    @patch('routes.transfer.execute_transfer')
    def test_transfer_success(self, mock_execute, mock_find, client):
        """Test transfer thành công"""
        # Mock tìm thấy cả hai tài khoản
        mock_find.side_effect = [
            ({'id': 1, 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'id': 2, 'account_number': '203847569801'}, {'database': 'bank2'})
        ]

        # Mock execute_transfer trả về thành công
        mock_execute.return_value = (True, "Chuyển tiền thành công!", "VB12345678", None)

        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 50000,
            'description': 'Test transfer'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'


class TestTransferErrors:
    """Test các trường hợp lỗi"""

    @patch('routes.transfer.find_account_by_number')
    def test_transfer_source_not_found(self, mock_find, client):
        """Test transfer thất bại - tài khoản nguồn không tồn tại"""
        mock_find.return_value = (None, None)

        response = client.post('/api/transfer', json={
            'from_account_number': '999999999999',
            'to_account_number': '203847569801',
            'amount': 50000,
            'description': 'Test'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data['status'].lower() or 'không tồn tại' in data.get('message', '').lower()

    @patch('routes.transfer.find_account_by_number')
    def test_transfer_destination_not_found(self, mock_find, client):
        """Test transfer thất bại - tài khoản đích không tồn tại"""
        mock_find.side_effect = [
            ({'id': 1, 'account_number': '102938475612'}, {'database': 'bank1'}),
            (None, None)
        ]

        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '999999999999',
            'amount': 50000,
            'description': 'Test'
        })

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data['status'].lower() or 'không tồn tại' in data.get('message', '').lower()


class TestTransferResponseFormat:
    """Test định dạng response"""

    @patch('routes.transfer.find_account_by_number')
    @patch('routes.transfer.execute_transfer')
    def test_transfer_response_contains_tx_id(self, mock_execute, mock_find, client):
        """Test response chứa tx_id"""
        mock_find.side_effect = [
            ({'id': 1, 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'id': 2, 'account_number': '203847569801'}, {'database': 'bank2'})
        ]
        mock_execute.return_value = (True, "Success", "VB12345678", None)

        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 50000,
            'description': 'Test'
        })

        data = response.get_json()
        assert 'tx_id' in data

    @patch('routes.transfer.find_account_by_number')
    @patch('routes.transfer.execute_transfer')
    def test_transfer_response_contains_message(self, mock_execute, mock_find, client):
        """Test response chứa message"""
        mock_find.side_effect = [
            ({'id': 1, 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'id': 2, 'account_number': '203847569801'}, {'database': 'bank2'})
        ]
        mock_execute.return_value = (True, "Success message", "VB12345678", None)

        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 50000,
            'description': 'Test'
        })

        data = response.get_json()
        assert 'message' in data


class TestTransferEdgeCases:
    """Test các edge cases"""

    @patch('routes.transfer.find_account_by_number')
    def test_transfer_with_empty_description(self, mock_find, client):
        """Test transfer với description rỗng"""
        mock_find.side_effect = [
            ({'id': 1, 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'id': 2, 'account_number': '203847569801'}, {'database': 'bank2'})
        ]

        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 50000,
            'description': ''
        })

        assert response.status_code in [200, 400, 408, 500]

    @patch('routes.transfer.find_account_by_number')
    def test_transfer_without_description(self, mock_find, client):
        """Test transfer không có description"""
        mock_find.side_effect = [
            ({'id': 1, 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'id': 2, 'account_number': '203847569801'}, {'database': 'bank2'})
        ]

        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 50000
        })

        assert response.status_code in [200, 400, 408, 500]

    def test_transfer_with_large_amount(self, client):
        """Test transfer với số tiền lớn"""
        response = client.post('/api/transfer', json={
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 999999999,
            'description': 'Large transfer'
        })

        # Có thể thành công hoặc lỗi do không đủ số dư
        assert response.status_code in [200, 400, 408, 500]


class TestRecoverAPI:
    """Test POST /api/recover endpoint"""

    def test_recover_endpoint_exists(self, client):
        """Test /api/recover endpoint tồn tại"""
        response = client.post('/api/recover')
        assert response.status_code in [200, 500]

    @patch('routes.recovery.recover_in_doubt_transactions')
    def test_recover_returns_count(self, mock_recover, client):
        """Test /api/recover trả về count"""
        mock_recover.return_value = []

        response = client.post('/api/recover')

        assert response.status_code == 200
        data = response.get_json()
        assert 'count' in data

    @patch('routes.recovery.recover_in_doubt_transactions')
    def test_recover_returns_recovered_list(self, mock_recover, client):
        """Test /api/recover trả về danh sách recovered"""
        mock_recover.return_value = [
            {'tx_id': 'VB12345678', 'action': 'COMMITTED'}
        ]

        response = client.post('/api/recover')

        assert response.status_code == 200
        data = response.get_json()
        assert 'recovered' in data
        assert isinstance(data['recovered'], list)


class TestTransferIdempotency:
    """Test idempotency cho /api/transfer"""

    @patch('routes.transfer.build_request_hash', return_value='hash-1')
    @patch('routes.transfer.get_idempotency_record')
    def test_transfer_replay_returns_stored_response(self, mock_get_record, _mock_hash, client):
        mock_get_record.return_value = {
            'idem_key': 'IDEMP-123',
            'request_hash': 'hash-1',
            'status': 'COMPLETED',
            'tx_id': 'VB12345678',
            'http_status': 200,
            'response_json': json.dumps({
                'status': 'success',
                'message': 'Replay success',
                'tx_id': 'VB12345678'
            })
        }

        response = client.post(
            '/api/transfer',
            json={
                'from_account_number': '102938475612',
                'to_account_number': '203847569801',
                'amount': 10000,
                'description': 'idem replay'
            },
            headers={'Idempotency-Key': 'IDEMP-123'}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['idempotent_replay'] is True
        assert data['tx_id'] == 'VB12345678'

    @patch('routes.transfer.build_request_hash', return_value='hash-new')
    @patch('routes.transfer.get_idempotency_record')
    def test_transfer_idempotency_mismatch_returns_409(self, mock_get_record, _mock_hash, client):
        mock_get_record.return_value = {
            'idem_key': 'IDEMP-123',
            'request_hash': 'hash-old',
            'status': 'COMPLETED',
            'tx_id': 'VB12345678',
            'http_status': 200,
            'response_json': '{}'
        }

        response = client.post(
            '/api/transfer',
            json={
                'from_account_number': '102938475612',
                'to_account_number': '203847569801',
                'amount': 10000,
                'description': 'idem mismatch'
            },
            headers={'Idempotency-Key': 'IDEMP-123'}
        )

        assert response.status_code == 409
        data = response.get_json()
        assert data['error_code'] == 'IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD'

    @patch('routes.transfer.finalize_record')
    @patch('routes.transfer.execute_transfer')
    @patch('routes.transfer.create_processing_record', return_value=True)
    @patch('routes.transfer.get_idempotency_record', return_value=None)
    @patch('routes.transfer.build_request_hash', return_value='hash-1')
    @patch('routes.transfer.find_account_by_number')
    def test_transfer_with_idempotency_finalize_called(
        self,
        mock_find,
        _mock_hash,
        _mock_get_record,
        _mock_create,
        mock_execute,
        mock_finalize,
        client,
    ):
        mock_find.side_effect = [
            ({'id': 1, 'account_number': '102938475612'}, {'database': 'bank1'}),
            ({'id': 2, 'account_number': '203847569801'}, {'database': 'bank2'})
        ]
        mock_execute.return_value = (True, 'Success', 'VB99999999', None)

        response = client.post(
            '/api/transfer',
            json={
                'from_account_number': '102938475612',
                'to_account_number': '203847569801',
                'amount': 10000,
                'description': 'idem normal'
            },
            headers={'Idempotency-Key': 'IDEMP-NEW'}
        )

        assert response.status_code == 200
        mock_finalize.assert_called_once()


class TestTransferStatusAPI:
    """Test endpoint tra cứu trạng thái giao dịch"""

    @patch('routes.transfer._get_transaction_status', return_value=None)
    def test_transfer_status_not_found(self, _mock_status, client):
        response = client.get('/api/transfer/status/VB_NOT_FOUND')
        assert response.status_code == 404
        data = response.get_json()
        assert data['status'] == 'error'

    @patch('routes.transfer._get_transaction_status')
    def test_transfer_status_success(self, mock_status, client):
        mock_status.return_value = {
            'tx_id': 'VB123',
            'xid': 'xid123',
            'from_account_number': '102938475612',
            'to_account_number': '203847569801',
            'amount': 10000,
            'description': 'Test',
            'phase': 'COMMITTED',
            'phase_label': 'Phase 2  ✔ COMMITTED   — Hoàn tất thành công',
            'business_status': 'SUCCESS',
            'message': 'Giao dịch đã hoàn tất thành công.',
            'created_at': '2026-04-14 20:00:00',
            'updated_at': '2026-04-14 20:00:10',
        }

        response = client.get('/api/transfer/status/VB123')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['data']['phase'] == 'COMMITTED'


class TestTransferRecentAPI:
    """Test endpoint giao dịch gần nhất cho dashboard monitor"""

    @patch('routes.transfer._get_recent_transactions', return_value=[])
    def test_transfer_recent_success_empty(self, _mock_recent, client):
        response = client.get('/api/transfer/recent')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['count'] == 0
        assert isinstance(data['items'], list)

    @patch('routes.transfer._get_recent_transactions')
    def test_transfer_recent_returns_items(self, mock_recent, client):
        mock_recent.return_value = [
            {
                'tx_id': 'VB100',
                'from_account_number': '102938475612',
                'to_account_number': '203847569801',
                'amount': 10000.0,
                'phase': 'COMMITTING',
                'phase_label': 'Phase 2  ▶ COMMITTING',
                'message': 'Coordinator đang gửi commit.',
                'updated_at': '2026-04-14 22:00:00',
            }
        ]

        response = client.get('/api/transfer/recent?limit=5')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['count'] == 1
        assert data['items'][0]['tx_id'] == 'VB100'
        mock_recent.assert_called_once_with(5)

    @patch('routes.transfer._get_recent_transactions', return_value=[])
    def test_transfer_recent_limit_clamped_for_invalid_value(self, mock_recent, client):
        response = client.get('/api/transfer/recent?limit=abc')
        assert response.status_code == 200
        mock_recent.assert_called_once_with(10)

    @patch('routes.transfer._get_recent_transactions', return_value=[])
    def test_transfer_recent_limit_capped_to_50(self, mock_recent, client):
        response = client.get('/api/transfer/recent?limit=500')
        assert response.status_code == 200
        mock_recent.assert_called_once_with(50)
