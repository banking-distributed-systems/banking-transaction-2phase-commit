"""
Module logging tập trung cho ứng dụng
"""

import logging
import os

# Đường dẫn tới .log ở thư mục gốc project (một cấp trên backend/)
_LOG_FILE = os.path.join(os.path.dirname(__file__), '..', '.log')
_LOG_FILE = os.path.normpath(_LOG_FILE)

_fmt = logging.Formatter(
    fmt='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# Cấu hình logging ra console VÀ file .log
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
    ]
)

# Thêm FileHandler ghi vào .log (append, UTF-8)
_file_handler = logging.FileHandler(_LOG_FILE, encoding='utf-8')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(_fmt)
logging.getLogger().addHandler(_file_handler)

# Logger chính cho 2PC
logger = logging.getLogger('2pc')


def get_logger(name: str = '2pc') -> logging.Logger:
    """
    Lấy logger theo tên

    Args:
        name: Tên logger

    Returns:
        Logger instance
    """
    return logging.getLogger(name)