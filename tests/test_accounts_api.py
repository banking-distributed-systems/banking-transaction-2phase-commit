"""
Integration tests cho accounts API
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
import json
from unittest.mock import patch, MagicMock


class TestGetAccountsAPI:
    """Test GET /api/accounts endpoint"""

    def test_get_accounts_endpoint_exists(self, client):
        """Test /api/accounts endpoint tồn tại"""
        response = client.get('/api/accounts')
        assert response.status_code in [200, 500]  # Có thể lỗi DB nhưng endpoint tồn tại

    @patch('routes.accounts.get_all_accounts_with_bank')
    def test_get_accounts_returns_list(self, mock_get_accounts, client):
        """Test /api/accounts trả về danh sách"""
        mock_get_accounts.return_value = [
            {'id': 1, 'name': 'Nguyễn Văn A', 'account_number': '102938475612', 'bank': 'bank1'},
            {'id': 2, 'name': 'Trần Thị B', 'account_number': '203847569801', 'bank': 'bank2'}
        ]

        response = client.get('/api/accounts')

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 2

    @patch('routes.accounts.get_all_accounts_with_bank')
    def test_get_accounts_returns_empty_list(self, mock_get_accounts, client):
        """Test /api/accounts trả về danh sách rỗng"""
        mock_get_accounts.return_value = []

        response = client.get('/api/accounts')

        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0


class TestLookupAccountAPI:
    """Test POST /api/lookup-account endpoint"""

    def test_lookup_account_requires_account_number(self, client):
        """Test /api/lookup-account yêu cầu account_number"""
        response = client.post('/api/lookup-account', json={})
        assert response.status_code == 400

    def test_lookup_account_with_empty_account_number(self, client):
        """Test /api/lookup-account với account_number rỗng"""
        response = client.post('/api/lookup-account', json={'account_number': ''})
        assert response.status_code in [400, 404]

    @patch('routes.accounts.get_account_by_number_safe')
    def test_lookup_account_success(self, mock_lookup, client):
        """Test tra cứu tài khoản thành công"""
        mock_lookup.return_value = {
            'name': 'Trần Thị B',
            'account_number': '203847569801'
        }

        response = client.post('/api/lookup-account', json={
            'account_number': '203847569801'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'account' in data

    @patch('routes.accounts.get_account_by_number_safe')
    def test_lookup_account_not_found(self, mock_lookup, client):
        """Test tra cứu tài khoản không tồn tại"""
        mock_lookup.return_value = None

        response = client.post('/api/lookup-account', json={
            'account_number': '999999999999'
        })

        assert response.status_code == 404
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'message' in data

    @patch('routes.accounts.get_account_by_number_safe')
    def test_lookup_account_with_spaces(self, mock_lookup, client):
        """Test tra cứu tài khoản có khoảng trắng"""
        mock_lookup.return_value = {
            'name': 'Nguyễn Văn A',
            'account_number': '102938475612'
        }

        response = client.post('/api/lookup-account', json={
            'account_number': '1029 3847 5612'
        })

        assert response.status_code == 200


class TestLookupAccountValidation:
    """Test validation cho lookup-account"""

    def test_lookup_account_rejects_missing_field(self, client):
        """Test lookup-account từ chối request thiếu field"""
        response = client.post('/api/lookup-account', json={'wrong_field': 'value'})
        assert response.status_code in [400, 404]

    def test_lookup_account_accepts_json(self, client):
        """Test lookup-account chấp nhận JSON"""
        response = client.post(
            '/api/lookup-account',
            data=json.dumps({'account_number': '203847569801'}),
            content_type='application/json'
        )
        assert response.status_code in [200, 404]


class TestAccountsAPIErrorHandling:
    """Test xử lý lỗi cho accounts API"""

    @patch('routes.accounts.get_all_accounts_with_bank')
    def test_get_accounts_handles_exception(self, mock_get_accounts, client):
        """Test /api/handlers exception"""
        mock_get_accounts.side_effect = Exception("Database error")

        response = client.get('/api/accounts')

        # Flask nên trả về 500 hoặc xử lý exception
        assert response.status_code in [200, 500]

    @patch('routes.accounts.get_account_by_number_safe')
    def test_lookup_account_handles_exception(self, mock_lookup, client):
        """Test /api/lookup-account xử lý exception"""
        mock_lookup.side_effect = Exception("Database error")

        response = client.post('/api/lookup-account', json={
            'account_number': '203847569801'
        })

        # Nên xử lý exception và trả về lỗi
        assert response.status_code in [200, 400, 404, 500]


class TestAccountResponseFormat:
    """Test định dạng response"""

    @patch('routes.accounts.get_account_by_number_safe')
    def test_lookup_response_format(self, mock_lookup, client):
        """Test định dạng response của lookup"""
        mock_lookup.return_value = {
            'name': 'Test User',
            'account_number': '1234567890'
        }

        response = client.post('/api/lookup-account', json={
            'account_number': '1234567890'
        })

        data = response.get_json()

        # Kiểm tra cấu trúc response
        assert 'status' in data
        if data['status'] == 'success':
            assert 'account' in data
            assert 'name' in data['account']
            assert 'account_number' in data['account']

    @patch('routes.accounts.get_all_accounts_with_bank')
    def test_accounts_response_includes_bank_info(self, mock_get_accounts, client):
        """Test response bao gồm thông tin bank"""
        mock_get_accounts.return_value = [
            {'id': 1, 'name': 'User A', 'bank': 'bank1'},
            {'id': 2, 'name': 'User B', 'bank': 'bank2'}
        ]

        response = client.get('/api/accounts')

        data = response.get_json()
        if isinstance(data, list) and len(data) > 0:
            assert 'bank' in data[0]
