from datetime import datetime, timezone
import random
from models import db

class Customer(db.Model):
    """Customer profile details and related banking accounts."""
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    customer_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), nullable=False, index=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(50), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    pincode = db.Column(db.String(10), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    kyc_status = db.Column(db.String(20), nullable=False, default='VERIFIED')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship('User', back_populates='customer')
    accounts = db.relationship('Account', back_populates='customer', lazy='dynamic', cascade='all, delete-orphan')
    beneficiaries = db.relationship('Beneficiary', back_populates='customer', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def primary_account(self):
        """Returns the first active account, or first account."""
        acc = self.accounts.filter_by(status='ACTIVE').first()
        if not acc:
            acc = self.accounts.first()
        return acc

    @property
    def total_balance(self):
        """Calculates combined balance across active accounts."""
        active_accs = self.accounts.filter_by(status='ACTIVE').all()
        return sum(float(acc.balance) for acc in active_accs)

    @classmethod
    def generate_customer_code(cls):
        """Generate unique 6-digit customer identifier e.g., CUST-729481."""
        while True:
            code = f"CUST-{random.randint(100000, 999999)}"
            if not cls.query.filter_by(customer_code=code).first():
                return code

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'customer_code': self.customer_code,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': self.phone,
            'email': self.user.email if self.user else None,
            'username': self.user.username if self.user else None,
            'address': self.address,
            'city': self.city,
            'state': self.state,
            'pincode': self.pincode,
            'date_of_birth': self.date_of_birth.strftime('%Y-%m-%d') if self.date_of_birth else None,
            'kyc_status': self.kyc_status,
            'is_active': self.user.is_active if self.user else True,
            'total_balance': self.total_balance,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<Customer {self.customer_code} ({self.full_name})>"
