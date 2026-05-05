"""
Tests cho authentication API theo schema mới.
"""

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestLoginAPI:
    def test_login_endpoint_exists(self, client):
        response = client.post('/api/login', json={'phone': '0901234567', 'password': '123456'})
        assert response.status_code in [200, 401, 500]

    def test_login_requires_phone(self, client):
        response = client.post('/api/login', json={})
        assert response.status_code == 400

    def test_login_requires_password(self, client):
        response = client.post('/api/login', json={'phone': '0901234567'})
        assert response.status_code == 400

    @patch('routes.auth.authenticate_user')
    def test_login_success(self, mock_authenticate, client):
        mock_authenticate.return_value = {
            'name': 'Nguyễn Văn A',
            'balance': 1000000,
            'account_number': '102938475612',
            'bank': 'bank1',
        }

        response = client.post('/api/login', json={'phone': '0901234567', 'password': '123456'})

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert data['user']['account_number'] == '102938475612'

    @patch('routes.auth.authenticate_user', return_value=None)
    def test_login_failure_account_not_found(self, _mock_authenticate, client):
        response = client.post('/api/login', json={'phone': '0901234567', 'password': 'wrong-password'})
        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'


class TestLoginValidation:
    def test_login_accepts_json_content_type(self, client):
        response = client.post(
            '/api/login',
            data=json.dumps({'phone': '0901234567', 'password': '123456'}),
            content_type='application/json',
        )
        assert response.status_code in [200, 401, 500]

    def test_login_rejects_form_body(self, client):
        response = client.post(
            '/api/login',
            data='phone=0901234567&password=123456',
            content_type='application/x-www-form-urlencoded',
        )
        assert response.status_code in [400, 415, 500]
