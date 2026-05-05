"""
Unit tests cho account_service theo schema mới.
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from account_service import (
    authenticate_user,
    find_account_by_number,
    get_account_by_number_safe,
    get_all_accounts_with_bank,
    save_transaction,
)
from config import DB1_CONFIG, DB2_CONFIG


class TestFindAccountByNumber:
    @patch('account_service.get_connection')
    def test_find_account_returns_none_for_empty_input(self, mock_get_conn):
        result, config = find_account_by_number(None)
        assert result is None
        assert config is None
        mock_get_conn.assert_not_called()

    @patch('account_service.get_connection')
    def test_find_account_returns_account_and_config(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'name': 'Nguyễn Văn A',
            'balance': 1000000,
            'account_number': '102938475612',
        }

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result, config = find_account_by_number('102938475612')

        assert result['account_number'] == '102938475612'
        assert config is not None

    @patch('account_service.get_connection')
    def test_find_account_handles_spaces_in_number(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'name': 'Test'}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        find_account_by_number('1029 3847 5612')
        sql = mock_cursor.execute.call_args[0][0]
        assert 'REPLACE(account_number' in sql

    @patch('account_service.get_connection')
    def test_find_account_searches_all_databases(self, mock_get_conn):
        cursor_1 = MagicMock()
        cursor_1.fetchone.return_value = None
        conn_1 = MagicMock()
        conn_1.cursor.return_value.__enter__ = Mock(return_value=cursor_1)
        conn_1.cursor.return_value.__exit__ = Mock(return_value=False)

        cursor_2 = MagicMock()
        cursor_2.fetchone.return_value = {'name': 'Test B', 'account_number': '203847569801'}
        conn_2 = MagicMock()
        conn_2.cursor.return_value.__enter__ = Mock(return_value=cursor_2)
        conn_2.cursor.return_value.__exit__ = Mock(return_value=False)

        mock_get_conn.side_effect = [conn_1, conn_2]

        result, config = find_account_by_number('203847569801')
        assert result['name'] == 'Test B'
        assert config == DB2_CONFIG


class TestAuthenticateUser:
    @patch('account_service.get_connection')
    def test_authenticate_user_returns_user_on_success(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            'name': 'Nguyễn Văn A',
            'balance': 1000000,
            'account_number': '102938475612',
            'account_type': None,
        }

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = authenticate_user('0901234567', '123456')
        assert result['bank'] == 'bank1'
        assert result['account_number'] == '102938475612'
        sql = mock_cursor.execute.call_args[0][0]
        assert 'REPLACE(phone' in sql

    @patch('account_service.get_connection')
    def test_authenticate_user_returns_none_on_failure(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        assert authenticate_user('0901234567', 'wrong-password') is None


class TestSaveTransaction:
    @patch('account_service.get_coordinator_conn')
    def test_save_transaction_returns_true_on_success(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = save_transaction(
            tx_id='VB12345678',
            from_acc={'account_number': '102938475612', 'name': 'Nguyễn Văn A'},
            to_acc={'account_number': '203847569801', 'name': 'Trần Thị B'},
            amount=50000,
            description='Test',
            status='COMMITTED',
        )

        assert result is True
        assert 'INSERT INTO transactions' in mock_cursor.execute.call_args[0][0]

    @patch('account_service.get_coordinator_conn', side_effect=Exception('Connection failed'))
    def test_save_transaction_returns_false_on_error(self, _mock_get_conn):
        result = save_transaction(
            tx_id='VB12345678',
            from_acc={'account_number': '102938475612', 'name': 'Nguyễn Văn A'},
            to_acc={'account_number': '203847569801', 'name': 'Trần Thị B'},
            amount=50000,
            description='Test',
            status='COMMITTED',
        )
        assert result is False


class TestGetAllAccountsWithBank:
    @patch('account_service.get_connection')
    def test_get_all_accounts_includes_bank_info(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'name': 'Test A', 'account_number': '102938475612', 'bank': 'Ngân hàng 1'},
            {'name': 'Test B', 'account_number': '203847569801', 'bank': 'Ngân hàng 2'},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = get_all_accounts_with_bank()
        assert len(result) >= 1
        assert 'bank' in result[0]


class TestGetAccountByNumberSafe:
    @patch('account_service.find_account_by_number')
    def test_get_account_by_number_safe_returns_account_info(self, mock_find):
        mock_find.return_value = (
            {'name': 'Nguyễn Văn A', 'account_number': '102938475612', 'balance': 1000000},
            DB1_CONFIG,
        )
        result = get_account_by_number_safe('102938475612')
        assert result == {'name': 'Nguyễn Văn A', 'account_number': '102938475612', 'account_type': None}

    @patch('account_service.find_account_by_number', return_value=(None, None))
    def test_get_account_by_number_safe_returns_none_when_not_found(self, _mock_find):
        assert get_account_by_number_safe('999999999999') is None
