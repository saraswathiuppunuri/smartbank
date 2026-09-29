from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User
from models.customer import Customer
from models.account import Account
from models.card import Card
from models.transaction import Transaction
from models.beneficiary import Beneficiary
from models.notification import Notification

__all__ = [
    'db',
    'User',
    'Customer',
    'Account',
    'Card',
    'Transaction',
    'Beneficiary',
    'Notification'
]
