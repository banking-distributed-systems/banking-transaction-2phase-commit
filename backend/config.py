"""
Cấu hình ứng dụng - Database config và constants
"""

import os

# ---------------------------------------------------------------------------
# Thời gian chờ tối đa (giây) cho Phase 1 (PREPARE) — Kịch bản 5
# ---------------------------------------------------------------------------
PREPARE_TIMEOUT = 10

# Database configurations
DB1_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'root',
    'database': 'bank1',
    'autocommit': False,
    'connect_timeout': 5,
    'read_timeout': 8,
    'write_timeout': 8
}

DB2_CONFIG = {
    'host': 'localhost',
    'port': 3307,
    'user': 'root',
    'password': 'root',
    'database': 'bank2',
    'autocommit': False,
    'connect_timeout': 5,
    'read_timeout': 8,
    'write_timeout': 8
}

DB3_CONFIG = {
    'host': 'localhost',
    'port': 3308,
    'user': 'root',
    'password': 'root',
    'database': 'bank3',
    'autocommit': False,
    'connect_timeout': 5,
    'read_timeout': 8,
    'write_timeout': 8
}

# Danh sách tất cả database configs
ALL_DB_CONFIGS = [DB1_CONFIG, DB2_CONFIG, DB3_CONFIG]

# ---------------------------------------------------------------------------
# File logger path
# ---------------------------------------------------------------------------
LOG_FILE = os.path.join(os.path.dirname(__file__), '..', '.log')

# ---------------------------------------------------------------------------
# Nhãn hiển thị cho từng phase trong 2PC
# ---------------------------------------------------------------------------
PHASE_LABELS = {
    'PREPARING':    'Phase 1  ▶ PREPARING   — TC bắt đầu giao dịch',
    'PREPARED':     'Phase 1  ✔ PREPARED    — Cả hai participant sẵn sàng',
    'COMMITTING':   'Phase 2  ▶ COMMITTING  — TC bắt đầu gửi COMMIT',
    'COMMIT_A':     'Phase 2  ⚡ COMMIT_A    — Bank A đã COMMIT, Bank B chưa',
    'COMMITTED':    'Phase 2  ✔ COMMITTED   — Hoàn tất thành công',
    'ABORTED':      'Phase *  ✖ ABORTED     — Giao dịch bị hủy (Rollback)',
    'TIMEOUT':      'Phase 1  ⏱ TIMEOUT     — Participant phản hồi quá chậm',
    'COMPENSATING': 'Recover  ↺ COMPENSATING — Đang hoàn tiền cho Bank A',
    'COMPENSATED':  'Recover  ✔ COMPENSATED  — Hoàn tiền thành công',
}