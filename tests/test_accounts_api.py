"""
Integration tests cho accounts API.
"""

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestGetAccountsAPI:
    def test_get_accounts_endpoint_exists(self, client):
        response = client.get('/api/accounts')
        assert response.status_code in [200, 500]

    @patch('routes.accounts.get_all_accounts_with_bank')
    def test_get_accounts_returns_list(self, mock_get_accounts, client):
        mock_get_accounts.return_value = [
            {'name': 'Nguyễn Văn A', 'account_number': '102938475612', 'balance': 1000, 'bank': 'Ngân hàng 1'},
            {'name': 'Trần Thị B', 'account_number': '203847569801', 'balance': 2000, 'bank': 'Ngân hàng 2'},
        ]
        response = client.get('/api/accounts')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert 'bank' in data[0]


class TestLookupAccountAPI:
    def test_lookup_account_requires_account_number(self, client):
        response = client.post('/api/lookup-account', json={})
        assert response.status_code == 400

    @patch('routes.accounts.get_account_by_number_safe')
    def test_lookup_account_success(self, mock_lookup, client):
        mock_lookup.return_value = {
            'name': 'Trần Thị B',
            'account_number': '203847569801',
        }
        response = client.post('/api/lookup-account', json={'account_number': '203847569801'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['account']['account_number'] == '203847569801'

    @patch('routes.accounts.get_account_by_number_safe', return_value=None)
    def test_lookup_account_not_found(self, _mock_lookup, client):
        response = client.post('/api/lookup-account', json={'account_number': '999999999999'})
        assert response.status_code == 404

    def test_lookup_account_accepts_json(self, client):
        response = client.post(
            '/api/lookup-account',
            data=json.dumps({'account_number': '203847569801'}),
            content_type='application/json',
        )
        assert response.status_code in [200, 404]
