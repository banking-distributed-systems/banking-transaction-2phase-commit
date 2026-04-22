"""
Unit tests cho config module.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from config import (
    ALL_DB_CONFIGS,
    COORDINATOR_DB_CONFIG,
    DB1_CONFIG,
    DB2_CONFIG,
    DB3_CONFIG,
    PHASE_LABELS,
    PREPARE_TIMEOUT,
)


class TestDatabaseConfig:
    def test_bank_configs_exist(self):
        assert DB1_CONFIG['database'] == 'bank1'
        assert DB2_CONFIG['database'] == 'bank2'
        assert DB3_CONFIG['database'] == 'bank3'

    def test_coordinator_config_exists(self):
        assert COORDINATOR_DB_CONFIG['database'] == 'coordinator'
        assert COORDINATOR_DB_CONFIG['port'] == 3309

    def test_all_db_configs_contains_three_bank_dbs(self):
        assert ALL_DB_CONFIGS == [DB1_CONFIG, DB2_CONFIG, DB3_CONFIG]

    def test_all_configs_have_required_fields(self):
        required = ['host', 'port', 'user', 'password', 'database', 'autocommit']
        for config in [DB1_CONFIG, DB2_CONFIG, DB3_CONFIG, COORDINATOR_DB_CONFIG]:
            for field in required:
                assert field in config


class TestPrepareTimeout:
    def test_prepare_timeout_is_reasonable(self):
        assert isinstance(PREPARE_TIMEOUT, int)
        assert 1 <= PREPARE_TIMEOUT <= 60


class TestPhaseLabels:
    def test_phase_labels_have_required_phases(self):
        for phase in ['PREPARING', 'PREPARED', 'COMMITTING', 'COMMIT_A', 'COMMITTED', 'ABORTED']:
            assert phase in PHASE_LABELS
