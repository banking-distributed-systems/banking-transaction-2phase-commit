"""
Unit tests cho database module theo schema mới.
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config import COORDINATOR_DB_CONFIG, DB1_CONFIG, DB2_CONFIG, DB3_CONFIG
from database import (
    execute_query,
    execute_query_autocommit,
    get_all_accounts,
    get_connection,
    get_coordinator_conn,
)


class TestGetConnection:
    @patch('database.pymysql.connect')
    def test_get_connection_returns_pymysql_connection(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        result = get_connection(DB1_CONFIG)
        assert result is mock_conn
        mock_connect.assert_called_once_with(**DB1_CONFIG)

    @patch('database.pymysql.connect', side_effect=Exception('Connection failed'))
    def test_get_connection_raises_exception_on_error(self, _mock_connect):
        with pytest.raises(Exception):
            get_connection(DB1_CONFIG)


class TestGetCoordinatorConn:
    @patch('database.get_connection')
    def test_get_coordinator_conn_returns_connection(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn
        assert get_coordinator_conn() is mock_conn

    @patch('database.get_connection')
    def test_get_coordinator_conn_uses_coordinator_config(self, mock_get_conn):
        mock_get_conn.return_value = MagicMock()
        get_coordinator_conn()
        called_config = mock_get_conn.call_args[1]
        assert called_config['database'] == COORDINATOR_DB_CONFIG['database']
        assert called_config['autocommit'] is True


class TestExecuteQuery:
    @patch('database.get_connection')
    def test_execute_query_fetch_one(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {'name': 'Test'}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn
        assert execute_query(DB1_CONFIG, 'SELECT 1', fetch_one=True) == {'name': 'Test'}

    @patch('database.get_connection')
    def test_execute_query_closes_connection(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn
        execute_query(DB1_CONFIG, 'SELECT 1')
        mock_conn.close.assert_called_once()


class TestExecuteQueryAutocommit:
    @patch('database.get_connection')
    def test_execute_query_autocommit_sets_autocommit_true(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn
        execute_query_autocommit(DB1_CONFIG, 'SELECT 1')
        called_config = mock_get_conn.call_args[1]
        assert called_config['autocommit'] is True


class TestGetAllAccounts:
    @patch('database.get_connection')
    def test_get_all_accounts_queries_all_databases(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn
        get_all_accounts()
        assert mock_get_conn.call_count == 3


class TestDatabaseConnectionIntegration:
    @pytest.mark.integration
    def test_db_connections_available(self):
        for config in (DB1_CONFIG, DB2_CONFIG, DB3_CONFIG, COORDINATOR_DB_CONFIG):
            try:
                conn = get_connection(config)
                assert conn is not None
                conn.close()
            except Exception as e:
                pytest.skip(f"{config['database']} not available: {e}")
