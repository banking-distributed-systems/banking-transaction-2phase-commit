"""
Module logging tập trung cho ứng dụng
"""

import logging

# Cấu hình logging chỉ ra console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
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