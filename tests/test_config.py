"""
Unit tests cho config module
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from config import (
    DB1_CONFIG,
    DB2_CONFIG,
    DB3_CONFIG,
    ALL_DB_CONFIGS,
    PREPARE_TIMEOUT,
    PHASE_LABELS
)


class TestDatabaseConfig:
    """Test database configurations"""

    def test_db1_config_exists(self):
        """Test DB1 config tồn tại"""
        assert DB1_CONFIG is not None
        assert DB1_CONFIG['database'] == 'bank1'

    def test_db1_config_has_required_fields(self):
        """Test DB1 config có đủ required fields"""
        required_fields = ['host', 'port', 'user', 'password', 'database', 'autocommit']
        for field in required_fields:
            assert field in DB1_CONFIG, f"Thiếu field: {field}"

    def test_db2_config_exists(self):
        """Test DB2 config tồn tại"""
        assert DB2_CONFIG is not None
        assert DB2_CONFIG['database'] == 'bank2'

    def test_db2_config_has_required_fields(self):
        """Test DB2 config có đủ required fields"""
        required_fields = ['host', 'port', 'user', 'password', 'database', 'autocommit']
        for field in required_fields:
            assert field in DB2_CONFIG, f"Thiếu field: {field}"

    def test_db3_config_exists(self):
        """Test DB3 config tồn tại"""
        assert DB3_CONFIG is not None
        assert DB3_CONFIG['database'] == 'bank3'

    def test_db3_config_has_required_fields(self):
        """Test DB3 config có đủ required fields"""
        required_fields = ['host', 'port', 'user', 'password', 'database', 'autocommit']
        for field in required_fields:
            assert field in DB3_CONFIG, f"Thiếu field: {field}"

    def test_all_db_configs_contains_all_dbs(self):
        """Test ALL_DB_CONFIGS chứa tất cả 3 database"""
        assert len(ALL_DB_CONFIGS) == 3

    def test_all_db_configs_contains_db1(self):
        """Test ALL_DB_CONFIGS chứa DB1"""
        assert DB1_CONFIG in ALL_DB_CONFIGS

    def test_all_db_configs_contains_db2(self):
        """Test ALL_DB_CONFIGS chứa DB2"""
        assert DB2_CONFIG in ALL_DB_CONFIGS

    def test_all_db_configs_contains_db3(self):
        """Test ALL_DB_CONFIGS chứa DB3"""
        assert DB3_CONFIG in ALL_DB_CONFIGS


class TestPrepareTimeout:
    """Test prepare timeout configuration"""

    def test_prepare_timeout_is_positive(self):
        """Test prepare timeout là số dương"""
        assert PREPARE_TIMEOUT > 0

    def test_prepare_timeout_is_integer(self):
        """Test prepare timeout là số nguyên"""
        assert isinstance(PREPARE_TIMEOUT, int)

    def test_prepare_timeout_reasonable_value(self):
        """Test prepare timeout có giá trị hợp lý (1-60 giây)"""
        assert 1 <= PREPARE_TIMEOUT <= 60


class TestPhaseLabels:
    """Test phase labels configuration"""

    def test_phase_labels_exists(self):
        """Test PHASE_LABELS tồn tại"""
        assert PHASE_LABELS is not None
        assert isinstance(PHASE_LABELS, dict)

    def test_phase_labels_has_required_phases(self):
        """Test PHASE_LABELS chứa các phase cần thiết"""
        required_phases = [
            'PREPARING',
            'PREPARED',
            'COMMITTING',
            'COMMIT_A',
            'COMMITTED',
            'ABORTED',
            'TIMEOUT',
            'COMPENSATING',
            'COMPENSATED'
        ]
        for phase in required_phases:
            assert phase in PHASE_LABELS, f"Thiếu phase: {phase}"

    def test_phase_labels_not_empty(self):
        """Test PHASE_LABELS không rỗng"""
        assert len(PHASE_LABELS) > 0


class TestDatabasePorts:
    """Test database ports configuration"""

    def test_db1_port_is_valid(self):
        """Test DB1 port hợp lệ"""
        assert 1 <= DB1_CONFIG['port'] <= 65535

    def test_db2_port_is_valid(self):
        """Test DB2 port hợp lệ"""
        assert 1 <= DB2_CONFIG['port'] <= 65535

    def test_db3_port_is_valid(self):
        """Test DB3 port hợp lệ"""
        assert 1 <= DB3_CONFIG['port'] <= 65535

    def test_db_ports_are_different(self):
        """Test các database dùng port khác nhau"""
        ports = [DB1_CONFIG['port'], DB2_CONFIG['port'], DB3_CONFIG['port']]
        assert len(set(ports)) == 3, "Các database nên dùng port khác nhau"


class TestDatabaseCredentials:
    """Test database credentials configuration"""

    def test_db1_autocommit_is_false(self):
        """Test DB1 autocommit = False (cần thiết cho XA transaction)"""
        assert DB1_CONFIG['autocommit'] == False

    def test_db2_autocommit_is_false(self):
        """Test DB2 autocommit = False"""
        assert DB2_CONFIG['autocommit'] == False

    def test_db3_autocommit_is_false(self):
        """Test DB3 autocommit = False"""
        assert DB3_CONFIG['autocommit'] == False

    def test_timeouts_configured(self):
        """Test timeout được cấu hình"""
        for config in ALL_DB_CONFIGS:
            assert 'connect_timeout' in config
            assert 'read_timeout' in config
            assert 'write_timeout' in config
