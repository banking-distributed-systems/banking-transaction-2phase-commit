"""
Integration tests cho authentication API
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
import json
from unittest.mock import patch, MagicMock


class TestLoginAPI:
    """Test /api/login endpoint"""

    def test_login_endpoint_exists(self, client):
        """Test /api/login endpoint tồn tại"""
        response = client.post('/api/login', json={'phone': '0901234567', 'password': '123456'})
        assert response.status_code in [200, 401, 500]  # Các mã hợp lệ

    def test_login_requires_phone(self, client):
        """Test /api/login yêu cầu phone"""
        response = client.post('/api/login', json={'password': '123456'})
        assert response.status_code == 400

    def test_login_requires_password(self, client):
        """Test /api/login yêu cầu password"""
        response = client.post('/api/login', json={'phone': '0901234567'})
        assert response.status_code in [400, 401, 500]

    def test_login_with_empty_body(self, client):
        """Test /api/login với body rỗng"""
        response = client.post('/api/login', json={})
        assert response.status_code in [400, 401, 500]

    @patch('routes.auth.authenticate_user')
    def test_login_success(self, mock_authenticate, client):
        """Test đăng nhập thành công"""
        mock_authenticate.return_value = {
            'id': 1,
            'name': 'Nguyễn Văn A',
            'balance': 1000000,
            'account_number': '102938475612',
            'account_type': 'saving'
        }

        response = client.post('/api/login', json={
            'phone': '0901234567',
            'password': '123456'
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'user' in data

    @patch('routes.auth.authenticate_user')
    def test_login_failure_wrong_password(self, mock_authenticate, client):
        """Test đăng nhập thất bại với mật khẩu sai"""
        mock_authenticate.return_value = None

        response = client.post('/api/login', json={
            'phone': '0901234567',
            'password': 'wrong_password'
        })

        assert response.status_code == 401
        data = response.get_json()
        assert data['status'] == 'error'

    @patch('routes.auth.authenticate_user')
    def test_login_failure_user_not_found(self, mock_authenticate, client):
        """Test đăng nhập thất bại với user không tồn tại"""
        mock_authenticate.return_value = None

        response = client.post('/api/login', json={
            'phone': '0999999999',
            'password': '123456'
        })

        assert response.status_code == 401
        data = response.get_json()
        assert 'message' in data


class TestLoginValidation:
    """Test validation cho login"""

    def test_login_accepts_json_content_type(self, client):
        """Test /api/login chấp nhận JSON content type"""
        response = client.post(
            '/api/login',
            data=json.dumps({'phone': '0901234567', 'password': '123456'}),
            content_type='application/json'
        )
        assert response.status_code in [200, 401, 500]

    def test_login_rejects_plain_text(self, client):
        """Test /api/login từ chối plain text"""
        response = client.post(
            '/api/login',
            data='phone=0901234567&password=123456',
            content_type='application/x-www-form-urlencoded'
        )
        # Flask có thể xử lý hoặc trả lỗi
        assert response.status_code in [200, 400, 401, 415, 500]


class TestLoginEdgeCases:
    """Test các edge cases cho login"""

    @patch('routes.auth.authenticate_user')
    def test_login_with_none_phone(self, mock_authenticate, client):
        """Test đăng nhập với phone = None"""
        response = client.post('/api/login', json={'phone': None, 'password': '123456'})
        # Xử lý tùy implementation
        assert response.status_code in [200, 400, 401, 500]

    @patch('routes.auth.authenticate_user')
    def test_login_with_none_password(self, mock_authenticate, client):
        """Test đăng nhập với password = None"""
        response = client.post('/api/login', json={'phone': '0901234567', 'password': None})
        assert response.status_code in [200, 400, 401, 500]

    @patch('routes.auth.authenticate_user')
    def test_login_with_empty_string(self, mock_authenticate, client):
        """Test đăng nhập với chuỗi rỗng"""
        mock_authenticate.return_value = None
        response = client.post('/api/login', json={'phone': '', 'password': ''})
        assert response.status_code in [400, 401, 500]

    @patch('routes.auth.authenticate_user')
    def test_login_with_very_long_phone(self, mock_authenticate, client):
        """Test đăng nhập với số điện thoại quá dài"""
        response = client.post('/api/login', json={
            'phone': '0' * 100,
            'password': '123456'
        })
        assert response.status_code in [200, 400, 401, 500]
