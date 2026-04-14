"""
Module logging tập trung cho ứng dụng
"""

import logging
from config import LOG_FILE

# Cấu hình logging - mode 'w' để ghi đè mỗi lần chạy
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8'),
        logging.StreamHandler(),  # vẫn in ra terminal
    ]
)

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