"""
Test fixtures cho V-Bank 2PC.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


TEST_ACCOUNT_A = {
    'account_number': '102938475612',
    'name': 'Nguyễn Văn A',
    'balance': 1234567890,
    'bank': 'bank1',
}

TEST_ACCOUNT_B = {
    'account_number': '203847569801',
    'name': 'Trần Thị B',
    'balance': 2000000,
    'bank': 'bank2',
}

TEST_ACCOUNT_C = {
    'account_number': '304756128934',
    'name': 'Lê Văn C',
    'balance': 8000000,
    'bank': 'bank3',
}

VALID_LOGIN_DATA = {
    'phone': '0901234567',
    'password': '123456',
}

INVALID_LOGIN_DATA = {
    'phone': '0901234567',
    'password': 'wrong-password',
}

VALID_TRANSFER_DATA = {
    'from_account_number': '102938475612',
    'to_account_number': '203847569801',
    'amount': 50000,
    'description': 'Test transfer',
}
