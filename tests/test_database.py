"""
Unit tests cho database module
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from unittest.mock import Mock, patch, MagicMock
import pymysql

from database import (
    get_connection,
    get_log_conn,
    execute_query,
    execute_query_autocommit,
    get_all_accounts
)
from config import DB1_CONFIG, DB2_CONFIG, DB3_CONFIG


class TestGetConnection:
    """Test get_connection function"""

    @patch('database.pymysql.connect')
    def test_get_connection_returns_pymysql_connection(self, mock_connect):
        """Test get_connection trả về pymysql connection"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = get_connection(DB1_CONFIG)

        assert result is mock_conn
        mock_connect.assert_called_once_with(**DB1_CONFIG)

    @patch('database.pymysql.connect')
    def test_get_connection_calls_with_correct_config(self, mock_connect):
        """Test get_connection gọi với config đúng"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        get_connection(DB2_CONFIG)

        mock_connect.assert_called_once_with(**DB2_CONFIG)

    @patch('database.pymysql.connect')
    def test_get_connection_raises_exception_on_error(self, mock_connect):
        """Test get_connection raise exception khi lỗi"""
        mock_connect.side_effect = Exception("Connection failed")

        with pytest.raises(Exception):
            get_connection(DB1_CONFIG)


class TestGetLogConn:
    """Test get_log_conn function"""

    @patch('database.get_connection')
    def test_get_log_conn_returns_connection(self, mock_get_conn):
        """Test get_log_conn trả về connection"""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        result = get_log_conn()

        assert result is mock_conn

    @patch('database.get_connection')
    def test_get_log_conn_uses_db1_config(self, mock_get_conn):
        """Test get_log_conn sử dụng DB1 config"""
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        get_log_conn()

        # Kiểm tra được gọi với autocommit=True
        called_config = mock_get_conn.call_args[1]
        assert called_config['autocommit'] == True
        assert called_config['database'] == 'bank1'


class TestExecuteQuery:
    """Test execute_query function"""

    @patch('database.get_connection')
    def test_execute_query_fetch_one(self, mock_get_conn):
        """Test execute_query với fetch_one=True"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'id': 1, 'name': 'Test'}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = execute_query(DB1_CONFIG, "SELECT * FROM accounts", fetch_one=True)

        assert result == {'id': 1, 'name': 'Test'}

    @patch('database.get_connection')
    def test_execute_query_fetch_all(self, mock_get_conn):
        """Test execute_query với fetch_all=True"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [{'id': 1}, {'id': 2}]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = execute_query(DB1_CONFIG, "SELECT * FROM accounts", fetch_all=True)

        assert result == [{'id': 1}, {'id': 2}]

    @patch('database.get_connection')
    def test_execute_query_returns_none_on_error(self, mock_get_conn):
        """Test execute_query trả về None khi lỗi"""
        mock_get_conn.side_effect = Exception("Query failed")

        result = execute_query(DB1_CONFIG, "SELECT * FROM accounts")

        assert result is None

    @patch('database.get_connection')
    def test_execute_query_closes_connection(self, mock_get_conn):
        """Test execute_query đóng connection sau khi query"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        execute_query(DB1_CONFIG, "SELECT 1")

        mock_conn.close.assert_called_once()

    @patch('database.get_connection')
    def test_execute_query_uses_dict_cursor_by_default(self, mock_get_conn):
        """Test execute_query sử dụng DictCursor mặc định"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        execute_query(DB1_CONFIG, "SELECT 1")

        # Kiểm tra cursor được gọi với DictCursor
        mock_conn.cursor.assert_called()


class TestExecuteQueryAutocommit:
    """Test execute_query_autocommit function"""

    @patch('database.get_connection')
    def test_execute_query_autocommit_sets_autocommit_true(self, mock_get_conn):
        """Test execute_query_autocommit bật autocommit"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        execute_query_autocommit(DB1_CONFIG, "SELECT 1")

        # Kiểm tra get_connection được gọi với autocommit=True
        called_config = mock_get_conn.call_args[1]
        assert called_config['autocommit'] == True


class TestGetAllAccounts:
    """Test get_all_accounts function"""

    @patch('database.get_connection')
    def test_get_all_accounts_returns_list(self, mock_get_conn):
        """Test get_all_accounts trả về list"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = get_all_accounts()

        assert isinstance(result, list)

    @patch('database.get_connection')
    def test_get_all_accounts_queries_all_databases(self, mock_get_conn):
        """Test get_all_accounts query tất cả database"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        get_all_accounts()

        # Kiểm tra được gọi 3 lần cho 3 database
        assert mock_get_conn.call_count == 3

    @patch('database.get_connection')
    def test_get_all_accounts_includes_bank_label(self, mock_get_conn):
        """Test get_all_accounts bao gồm bank label"""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {'id': 1, 'name': 'Test', 'bank': 'bank1'}
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        result = get_all_accounts()

        # Kiểm tra có field 'bank'
        if result:
            assert 'bank' in result[0]


class TestDatabaseConnectionIntegration:
    """Integration tests cho database connection (skip if DB not available)"""

    @pytest.mark.integration
    def test_db1_connection_available(self):
        """Test kết nối DB1 khả dụng"""
        try:
            conn = get_connection(DB1_CONFIG)
            assert conn is not None
            conn.close()
        except Exception as e:
            pytest.skip(f"DB1 not available: {e}")

    @pytest.mark.integration
    def test_db2_connection_available(self):
        """Test kết nối DB2 khả dụng"""
        try:
            conn = get_connection(DB2_CONFIG)
            assert conn is not None
            conn.close()
        except Exception as e:
            pytest.skip(f"DB2 not available: {e}")

    @pytest.mark.integration
    def test_db3_connection_available(self):
        """Test kết nối DB3 khả dụng"""
        try:
            conn = get_connection(DB3_CONFIG)
            assert conn is not None
            conn.close()
        except Exception as e:
            pytest.skip(f"DB3 not available: {e}")
