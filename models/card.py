from datetime import datetime, timezone, timedelta
import random
from werkzeug.security import generate_password_hash, check_password_hash
from models import db

class Card(db.Model):
    """Debit Card model linked to a customer bank account."""
    __tablename__ = 'cards'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    card_number = db.Column(db.String(19), unique=True, nullable=False, index=True)
    card_holder_name = db.Column(db.String(100), nullable=False)
    card_network = db.Column(db.String(20), nullable=False, default='VISA')  # VISA, MASTERCARD, RUPAY
    card_type = db.Column(db.String(20), nullable=False, default='Platinum')  # Platinum, Classic, Business
    expiry_month = db.Column(db.Integer, nullable=False)
    expiry_year = db.Column(db.Integer, nullable=False)
    cvv = db.Column(db.String(4), nullable=False)
    pin_hash = db.Column(db.String(255), nullable=False)
    daily_limit = db.Column(db.Numeric(15, 2), nullable=False, default=50000.00)
    status = db.Column(db.String(20), nullable=False, default='ACTIVE', index=True)  # ACTIVE, LOCKED, BLOCKED, EXPIRED
    is_online_enabled = db.Column(db.Boolean, nullable=False, default=True)
    is_contactless_enabled = db.Column(db.Boolean, nullable=False, default=True)
    is_international_enabled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    account = db.relationship('Account', back_populates='cards')
    transactions = db.relationship('Transaction', back_populates='card', lazy='dynamic')

    def set_pin(self, pin):
        """Hash and set 4-digit ATM/POS PIN."""
        self.pin_hash = generate_password_hash(str(pin).strip())

    def check_pin(self, pin):
        """Verify plain text PIN against stored hash."""
        return check_password_hash(self.pin_hash, str(pin).strip())

    @classmethod
    def generate_card_number(cls, network='VISA'):
        """Generate unique 16-digit debit card number based on network standard."""
        prefixes = {
            'VISA': '4532',
            'MASTERCARD': '5421',
            'RUPAY': '6071'
        }
        prefix = prefixes.get(network.upper(), '4532')
        while True:
            # Prefix (4 digits) + 12 random digits = 16 digits
            middle_and_end = ''.join([str(random.randint(0, 9)) for _ in range(12)])
            raw_number = f"{prefix}{middle_and_end}"
            if not cls.query.filter_by(card_number=raw_number).first():
                return raw_number

    @classmethod
    def generate_cvv(cls):
        """Generate 3-digit CVV security code."""
        return f"{random.randint(100, 999)}"

    @property
    def formatted_card_number(self):
        """Format 16 digits into spaced 4-digit chunks: 4532 8910 2345 6789"""
        raw = self.card_number.replace(' ', '')
        return ' '.join([raw[i:i+4] for i in range(0, len(raw), 4)])

    @property
    def masked_card_number(self):
        """Display masked format for security: •••• •••• •••• 6789"""
        raw = self.card_number.replace(' ', '')
        if len(raw) >= 4:
            return f"•••• •••• •••• {raw[-4:]}"
        return raw

    @property
    def expiry_display(self):
        """Returns MM/YY format e.g. 09/29"""
        yy = str(self.expiry_year)[-2:]
        return f"{self.expiry_month:02d}/{yy}"

    @property
    def is_active(self):
        return self.status == 'ACTIVE'

    @property
    def is_locked(self):
        return self.status == 'LOCKED'

    @property
    def is_blocked(self):
        return self.status == 'BLOCKED'

    @property
    def status_badge_class(self):
        if self.status == 'ACTIVE':
            return 'bg-success text-white'
        elif self.status == 'LOCKED':
            return 'bg-warning text-dark'
        elif self.status == 'BLOCKED':
            return 'bg-danger text-white'
        return 'bg-secondary text-white'

    @property
    def spent_today(self):
        """Calculate total amount spent using this card today."""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        from models.transaction import Transaction
        txns = self.transactions.filter(
            Transaction.created_at >= today_start,
            Transaction.status == 'COMPLETED'
        ).all()
        return sum(float(t.amount) for t in txns)

    @property
    def remaining_daily_limit(self):
        """Calculate remaining daily spending limit for today."""
        rem = float(self.daily_limit) - self.spent_today
        return max(0.0, rem)

    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'account_id': self.account_id,
            'account_number': self.account.account_number if self.account else None,
            'card_holder_name': self.card_holder_name,
            'card_network': self.card_network,
            'card_type': self.card_type,
            'masked_card_number': self.masked_card_number,
            'expiry': self.expiry_display,
            'daily_limit': float(self.daily_limit),
            'spent_today': self.spent_today,
            'remaining_limit': self.remaining_daily_limit,
            'status': self.status,
            'is_online_enabled': self.is_online_enabled,
            'is_contactless_enabled': self.is_contactless_enabled,
            'is_international_enabled': self.is_international_enabled,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
        if include_sensitive:
            data['card_number'] = self.card_number
            data['formatted_card_number'] = self.formatted_card_number
            data['cvv'] = self.cvv
            data['expiry_month'] = self.expiry_month
            data['expiry_year'] = self.expiry_year
        return data

    def __repr__(self):
        return f"<Card {self.masked_card_number} ({self.card_network}) - {self.status}>"
