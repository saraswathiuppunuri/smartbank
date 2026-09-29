from datetime import datetime, timezone
import random
import string
from models import db

class Transaction(db.Model):
    """Transaction audit ledger model."""
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_ref = db.Column(db.String(35), unique=True, nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id', ondelete='RESTRICT'), nullable=False, index=True)
    card_id = db.Column(db.Integer, db.ForeignKey('cards.id', ondelete='SET NULL'), nullable=True, index=True)
    transaction_type = db.Column(db.String(30), nullable=False, index=True)  # DEPOSIT, WITHDRAWAL, TRANSFER_SENT, TRANSFER_RECEIVED, CARD_PAYMENT, ATM_WITHDRAWAL
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    balance_after = db.Column(db.Numeric(15, 2), nullable=False)
    recipient_account = db.Column(db.String(35), nullable=True)
    description = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='COMPLETED')  # COMPLETED, FAILED, PENDING
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    account = db.relationship('Account', back_populates='transactions')
    card = db.relationship('Card', back_populates='transactions')

    @classmethod
    def generate_txn_ref(cls, prefix="TXN"):
        """Generate unique transaction reference ID like TXN202609281248019482."""
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        rand_str = ''.join(random.choices(string.digits, k=4))
        return f"{prefix}{timestamp}{rand_str}"

    @property
    def is_credit(self):
        return self.transaction_type in ('DEPOSIT', 'TRANSFER_RECEIVED')

    @property
    def is_debit(self):
        return self.transaction_type in ('WITHDRAWAL', 'TRANSFER_SENT', 'CARD_PAYMENT', 'ATM_WITHDRAWAL', 'BRANCH_WITHDRAWAL')

    @property
    def badge_class(self):
        mapping = {
            'DEPOSIT': 'bg-success',
            'TRANSFER_RECEIVED': 'bg-primary',
            'WITHDRAWAL': 'bg-danger',
            'TRANSFER_SENT': 'bg-warning text-dark',
            'CARD_PAYMENT': 'bg-dark text-white',
            'ATM_WITHDRAWAL': 'bg-danger text-white',
            'BRANCH_WITHDRAWAL': 'bg-info text-dark'
        }
        return mapping.get(self.transaction_type, 'bg-secondary')

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_ref': self.transaction_ref,
            'account_id': self.account_id,
            'account_number': self.account.account_number if self.account else None,
            'transaction_type': self.transaction_type,
            'amount': float(self.amount),
            'balance_after': float(self.balance_after),
            'recipient_account': self.recipient_account,
            'card_id': self.card_id,
            'card_masked_number': self.card.masked_card_number if self.card else None,
            'description': self.description,
            'status': self.status,
            'is_credit': self.is_credit,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<Transaction {self.transaction_ref} - {self.transaction_type} ₹{self.amount}>"
