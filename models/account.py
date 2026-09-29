from datetime import datetime, timezone
import random
from models import db

class Account(db.Model):
    """Bank account model supporting Savings, Current, and Salary accounts."""
    __tablename__ = 'accounts'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='RESTRICT'), nullable=False, index=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    account_type = db.Column(db.String(20), nullable=False, default='Savings')  # Savings, Current, Salary
    balance = db.Column(db.Numeric(15, 2), nullable=False, default=0.00)
    status = db.Column(db.String(20), nullable=False, default='ACTIVE', index=True)  # ACTIVE, INACTIVE, SUSPENDED
    currency = db.Column(db.String(5), nullable=False, default='INR')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    customer = db.relationship('Customer', back_populates='accounts')
    transactions = db.relationship('Transaction', back_populates='account', lazy='dynamic', cascade='all, delete-orphan')
    cards = db.relationship('Card', back_populates='account', lazy='dynamic', cascade='all, delete-orphan')

    @classmethod
    def generate_account_number(cls):
        """Generate unique 12-digit account number starting with 1001."""
        while True:
            # 1001 + 8 random digits = 12 digits total
            suffix = ''.join([str(random.randint(0, 9)) for _ in range(8)])
            acc_num = f"1001{suffix}"
            if not cls.query.filter_by(account_number=acc_num).first():
                return acc_num

    @property
    def is_active(self):
        return self.status == 'ACTIVE'

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'customer_name': self.customer.full_name if self.customer else None,
            'account_number': self.account_number,
            'account_type': self.account_type,
            'balance': float(self.balance),
            'status': self.status,
            'currency': self.currency,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

    def __repr__(self):
        return f"<Account {self.account_number} ({self.account_type}) - ₹{self.balance}>"
