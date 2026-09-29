from datetime import datetime, timezone
from models import db

class Beneficiary(db.Model):
    """Saved beneficiary/payee for fund transfers."""
    __tablename__ = 'beneficiaries'

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(30), nullable=False, index=True)
    bank_name = db.Column(db.String(100), nullable=False)
    ifsc_code = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    customer = db.relationship('Customer', back_populates='beneficiaries')

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'name': self.name,
            'account_number': self.account_number,
            'bank_name': self.bank_name,
            'ifsc_code': self.ifsc_code,
            'email': self.email,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<Beneficiary {self.name} - {self.account_number} ({self.bank_name})>"
