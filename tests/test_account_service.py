"""
Unit tests cho account_service module
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from unittest.mock import Mock, patch, MagicMock
import hashlib

from account_service import (
    find_account_by_number,
    authenticate_user,
    save_transaction,
    get_all_accounts_with_bank,
    get_account_by_number_safe
)
from config import DB1_CONFIG, DB2_CONFIG, ALL_DB_CONFIGS


class TestFindAccountByNumber:
    """Test find_account_by_number function"""

    @patch('account_service.get_connection')
    def test_find_account_returns_account_and_config(self, mock_get_conn):
        """Test find_account_by_number trả về account và config"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'name': 'Nguyễn Văn A',
            'balance': 1000000,
            'account_number': '102938475612',
            'account_type': 'saving'
        }

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result, config = find_account_by_number('102938475612')

        assert result is not None
        assert result['name'] == 'Nguyễn Văn A'
        assert config is not None

    @patch('account_service.get_connection')
    def test_find_account_handles_spaces_in_number(self, mock_get_conn):
        """Test find_account_by_number xử lý số tài khoản có khoảng trắng"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 1, 'name': 'Test'}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        find_account_by_number('1029 3847 5612')

        # Kiểm tra khoảng trắng được loại bỏ
        call_args = mock_cursor.execute.call_args
        assert 'REPLACE(account_number, ' in call_args[0][0]

    @patch('account_service.get_connection')
    def test_find_account_returns_none_when_not_found(self, mock_get_conn):
        """Test find_account_by_number trả về (None, None) khi không tìm thấy"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result, config = find_account_by_number('999999999999')

        assert result is None
        assert config is None

    @patch('account_service.get_connection')
    def test_find_account_searches_all_databases(self, mock_get_conn):
        """Test find_account_by_number tìm kiếm tất cả database"""
        # Giả lập DB1 không có, DB2 có
        mock_cursor_1 = MagicMock()
        mock_cursor_1.fetchone.return_value = None

        mock_cursor_2 = MagicMock()
        mock_cursor_2.fetchone.return_value = {'id': 2, 'name': 'Test B'}

        mock_conn_1 = MagicMock()
        mock_conn_1.cursor.return_value.__enter__ = Mock(return_value=mock_cursor_1)
        mock_conn_1.cursor.return_value.__exit__ = Mock(return_value=False)

        mock_conn_2 = MagicMock()
        mock_conn_2.cursor.return_value.__enter__ = Mock(return_value=mock_cursor_2)
        mock_conn_2.cursor.return_value.__exit__ = Mock(return_value=False)

        mock_get_conn.side_effect = [mock_conn_1, mock_conn_2]

        result, config = find_account_by_number('203847569801')

        assert result is not None
        assert result['name'] == 'Test B'


class TestAuthenticateUser:
    """Test authenticate_user function"""

    @patch('account_service.get_connection')
    def test_authenticate_user_returns_user_on_success(self, mock_get_conn):
        """Test authenticate_user trả về user khi đăng nhập thành công"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'id': 1,
            'name': 'Nguyễn Văn A',
            'balance': 1000000,
            'account_number': '102938475612',
            'account_type': 'saving'
        }

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = authenticate_user('0901234567', '123456')

        assert result is not None
        assert result['name'] == 'Nguyễn Văn A'

    @patch('account_service.get_connection')
    def test_authenticate_user_returns_none_on_failure(self, mock_get_conn):
        """Test authenticate_user trả về None khi đăng nhập thất bại"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = authenticate_user('0901234567', 'wrong_password')

        assert result is None

    @patch('account_service.get_connection')
    def test_authenticate_user_hashes_password(self, mock_get_conn):
        """Test authenticate_user hash password bằng MD5"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 1}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        authenticate_user('0901234567', '123456')

        # Kiểm tra password được hash
        call_args = mock_cursor.execute.call_args
        password_in_query = call_args[0][1][1]
        expected_hash = hashlib.md5('123456'.encode()).hexdigest()

        assert password_in_query == expected_hash


class TestSaveTransaction:
    """Test save_transaction function"""

    @patch('account_service.get_log_conn')
    def test_save_transaction_returns_true_on_success(self, mock_get_log_conn):
        """Test save_transaction trả về True khi lưu thành công"""
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_log_conn.return_value = mock_conn

        from_acc = {'account_number': '102938475612', 'name': 'Nguyễn Văn A'}
        to_acc = {'account_number': '203847569801', 'name': 'Trần Thị B'}

        result = save_transaction(
            tx_id='VB12345678',
            from_acc=from_acc,
            to_acc=to_acc,
            amount=50000,
            description='Test',
            status='SUCCESS'
        )

        assert result is True

    @patch('account_service.get_log_conn')
    def test_save_transaction_returns_false_on_error(self, mock_get_log_conn):
        """Test save_transaction trả về False khi lỗi"""
        mock_get_log_conn.side_effect = Exception("Connection failed")

        from_acc = {'account_number': '102938475612', 'name': 'Nguyễn Văn A'}
        to_acc = {'account_number': '203847569801', 'name': 'Trần Thị B'}

        result = save_transaction(
            tx_id='VB12345678',
            from_acc=from_acc,
            to_acc=to_acc,
            amount=50000,
            description='Test',
            status='SUCCESS'
        )

        assert result is False


class TestGetAllAccountsWithBank:
    """Test get_all_accounts_with_bank function"""

    @patch('account_service.get_connection')
    def test_get_all_accounts_returns_list(self, mock_get_conn):
        """Test get_all_accounts_with_bank trả về list"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = get_all_accounts_with_bank()

        assert isinstance(result, list)

    @patch('account_service.get_connection')
    def test_get_all_accounts_includes_bank_info(self, mock_get_conn):
        """Test get_all_accounts_with_bank bao gồm thông tin bank"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'name': 'Test A', 'bank': 'bank1'},
            {'id': 2, 'name': 'Test B', 'bank': 'bank2'}
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = get_all_accounts_with_bank()

        assert len(result) == 2


class TestGetAccountByNumberSafe:
    """Test get_account_by_number_safe function"""

    @patch('account_service.find_account_by_number')
    def test_get_account_by_number_safe_returns_account_info(self, mock_find):
        """Test get_account_by_number_safe trả về thông tin an toàn"""
        mock_find.return_value = (
            {'id': 1, 'name': 'Nguyễn Văn A', 'account_number': '102938475612'},
            DB1_CONFIG
        )

        result = get_account_by_number_safe('102938475612')

        assert result is not None
        assert 'name' in result
        assert 'account_number' in result

    @patch('account_service.find_account_by_number')
    def test_get_account_by_number_safe_returns_none_when_not_found(self, mock_find):
        """Test get_account_by_number_safe trả về None khi không tìm thấy"""
        mock_find.return_value = (None, None)

        result = get_account_by_number_safe('999999999999')

        assert result is None

    @patch('account_service.find_account_by_number')
    def test_get_account_by_number_safe_excludes_sensitive_data(self, mock_find):
        """Test get_account_by_number_safe không trả về dữ liệu nhạy cảm"""
        mock_find.return_value = (
            {'id': 1, 'name': 'Nguyễn Văn A', 'account_number': '102938475612', 'balance': 1000000, 'password': 'secret'},
            DB1_CONFIG
        )

        result = get_account_by_number_safe('102938475612')

        assert 'password' not in result
        assert 'balance' not in result
