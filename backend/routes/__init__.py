"""
Routes package - đăng ký tất cả blueprints
"""

from flask import Flask

from routes.auth import auth_bp
from routes.accounts import accounts_bp
from routes.transfer import transfer_bp
from routes.recovery import recovery_bp


def register_routes(app: Flask):
    """
    Đăng ký tất cả routes vào Flask app

    Args:
        app: Flask application instance
    """
    app.register_blueprint(auth_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(transfer_bp)
    app.register_blueprint(recovery_bp)
