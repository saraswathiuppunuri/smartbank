from routes.auth import auth_bp
from routes.customer import customer_bp
from routes.admin import admin_bp
from routes.transaction import transaction_bp
from routes.card import card_bp
from routes.api import api_bp

__all__ = [
    'auth_bp',
    'customer_bp',
    'admin_bp',
    'transaction_bp',
    'card_bp',
    'api_bp'
]
