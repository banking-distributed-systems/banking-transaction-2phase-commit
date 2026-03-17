"""
Test fixtures cho V-Bank 2PC
"""

import pytest
import sys
import os

# Thêm backend vào path để import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from flask import Flask
from app import app


@pytest.fixture
def client():
    """Flask test client fixture"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def app_instance():
    """Flask app instance fixture"""
    app.config['TESTING'] = True
    return app


# Dữ liệu test
TEST_ACCOUNT_A = {
    'account_number': '102938475612',
    'name': 'Nguyễn Văn A',
    'phone': '0901234567',
    'password': '123456'
}

TEST_ACCOUNT_B = {
    'account_number': '203847569801',
    'name': 'Trần Thị B',
    'phone': '0912345678',
    'password': '123456'
}

TEST_ACCOUNT_C = {
    'account_number': '304756128934',
    'name': 'Lê Văn C',
    'phone': '0923456789',
    'password': '123456'
}

VALID_LOGIN_DATA = {
    'phone': '0901234567',
    'password': '123456'
}

INVALID_LOGIN_DATA = {
    'phone': '0901234567',
    'password': 'wrong_password'
}

VALID_TRANSFER_DATA = {
    'from_account_number': '102938475612',
    'to_account_number': '203847569801',
    'amount': 50000,
    'description': 'Test transfer'
}

INVALID_TRANSFER_SAME_ACCOUNT = {
    'from_account_number': '102938475612',
    'to_account_number': '102938475612',
    'amount': 50000,
    'description': 'Test transfer'
}

INVALID_TRANSFER_NEGATIVE_AMOUNT = {
    'from_account_number': '102938475612',
    'to_account_number': '203847569801',
    'amount': -50000,
    'description': 'Test transfer'
}
