from datetime import datetime, timezone, date
import random
import string
from models import db

class BranchCashRequest(db.Model):
    """Digital Cash Withdrawal Slip / Pre-Booking for branch visits."""
    __tablename__ = 'branch_cash_requests'

    id = db.Column(db.Integer, primary_key=True)
    token_number = db.Column(db.String(35), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False, index=True)
    account_holder_name = db.Column(db.String(100), nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False, index=True)
    branch_code = db.Column(db.String(20), nullable=False, index=True)
    branch_name = db.Column(db.String(100), nullable=False)
    ifsc_code = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    amount_words = db.Column(db.String(255), nullable=True)
    visit_date = db.Column(db.Date, nullable=False, index=True)
    time_slot = db.Column(db.String(50), nullable=False)
    purpose = db.Column(db.String(150), nullable=False)
    denomination_preference = db.Column(db.String(255), nullable=True)
    signature_data = db.Column(db.Text, nullable=True)  # Base64 canvas data or typed signature
    status = db.Column(db.String(20), nullable=False, default='PENDING', index=True)  # PENDING, APPROVED, REJECTED, COLLECTED, EXPIRED
    priority_counter = db.Column(db.String(50), nullable=True)  # e.g., "Counter 2 (Fast-Track Cash)"
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    manager_remarks = db.Column(db.String(255), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    collected_at = db.Column(db.DateTime, nullable=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    customer = db.relationship('Customer', backref=db.backref('cash_requests', lazy='dynamic', cascade='all, delete-orphan'))
    account = db.relationship('Account', backref=db.backref('cash_requests', lazy='dynamic', cascade='all, delete-orphan'))
    manager = db.relationship('User', foreign_keys=[manager_id])
    transaction = db.relationship('Transaction', foreign_keys=[transaction_id])

    # Branch Information Catalog
    BRANCHES = {
        'KPHB': {
            'code': 'KPHB',
            'name': 'KPHB Colony Branch',
            'ifsc': 'SMRT000KPHB',
            'address': 'Plot 42, Road No. 1, KPHB Phase 1, Kukatpally, Hyderabad - 500072',
            'city': 'Hyderabad',
            'phone': '+91 40 2315 8890',
            'email': 'kphb@smartbank.com',
            'manager_name': 'K. Ramanathan',
            'counters': ['Counter 1 (General Banking)', 'Counter 2 (Fast-Track Cash)', 'Counter 3 (High-Value Privileged)']
        },
        'AMEERPET': {
            'code': 'AMEERPET',
            'name': 'Ameerpet Main Branch',
            'ifsc': 'SMRT000AMRP',
            'address': 'Metro Pillar A-1042, Opp. Big Bazaar, Ameerpet, Hyderabad - 500016',
            'city': 'Hyderabad',
            'phone': '+91 40 2374 4455',
            'email': 'ameerpet@smartbank.com',
            'manager_name': 'S. V. Rao',
            'counters': ['Counter 1 (General Banking)', 'Counter 2 (Fast-Track Cash)', 'Counter 4 (Priority Counter)']
        },
        'HITECH': {
            'code': 'HITECH',
            'name': 'Hitech City Cyber Gateway Branch',
            'ifsc': 'SMRT000HTEC',
            'address': 'Ground Floor, Cyber Gateway, Hitech City, Madhapur, Hyderabad - 500081',
            'city': 'Hyderabad',
            'phone': '+91 40 4012 3344',
            'email': 'hitech@smartbank.com',
            'manager_name': 'Anjali Desai',
            'counters': ['Counter 1 (Corporate Desk)', 'Counter 2 (Executive Cash)', 'Counter 3 (Express Desk)']
        },
        'GACHIBOWLI': {
            'code': 'GACHIBOWLI',
            'name': 'Gachibowli Financial District Branch',
            'ifsc': 'SMRT000GCBL',
            'address': 'Tower B, Financial District, Nanakramguda, Gachibowli, Hyderabad - 500032',
            'city': 'Hyderabad',
            'phone': '+91 40 4678 1200',
            'email': 'gachibowli@smartbank.com',
            'manager_name': 'Vikramaditya Roy',
            'counters': ['Counter 1 (General Banking)', 'Counter 2 (High-Value Cash Desk)', 'Counter 3 (Privilege Banking)']
        },
        'BANJARA': {
            'code': 'BANJARA',
            'name': 'Banjara Hills Elite Branch',
            'ifsc': 'SMRT000BNJR',
            'address': 'Road No. 2, Near Park Hyatt, Banjara Hills, Hyderabad - 500034',
            'city': 'Hyderabad',
            'phone': '+91 40 2355 6789',
            'email': 'banjarahills@smartbank.com',
            'manager_name': 'Pooja Reddy',
            'counters': ['Counter 1 (General Desk)', 'Counter 2 (VIP Cash Desk)', 'Counter 3 (Wealth Management)']
        }
    }

    TIME_SLOTS = [
        'Morning: 10:00 AM - 12:00 PM',
        'Afternoon: 12:00 PM - 02:00 PM',
        'Evening: 02:00 PM - 04:00 PM'
    ]

    PURPOSES = [
        'Personal Savings Withdrawal',
        'Real Estate / Property Advance',
        'Business / Commercial Expenditure',
        'Medical / Hospital Emergency',
        'Wedding / Family Event Ceremony',
        'Education / College Fee Payment',
        'Agricultural / Land Purchase',
        'Vehicle Purchase Downpayment',
        'Other Essential Cash Need'
    ]

    @classmethod
    def generate_token(cls, branch_code='KPHB'):
        """Generate unique fast-track token like CS-KPHB-20260929-8421."""
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d')
        branch_prefix = branch_code.upper()[:6]
        while True:
            rand_code = ''.join(random.choices(string.digits, k=4))
            token = f"CS-{branch_prefix}-{date_str}-{rand_code}"
            if not cls.query.filter_by(token_number=token).first():
                return token

    @classmethod
    def amount_to_words(cls, num):
        """Convert Indian currency amount to words (e.g. 50000 -> Fifty Thousand Rupees Only)."""
        try:
            n = int(num)
            if n == 0:
                return "Zero Rupees Only"

            ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
                    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
                    "Seventeen", "Eighteen", "Nineteen"]
            tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

            def convert_below_thousand(val):
                res = []
                if val >= 100:
                    res.append(ones[val // 100] + " Hundred")
                    val %= 100
                if val >= 20:
                    res.append(tens[val // 10])
                    val %= 10
                if val > 0:
                    res.append(ones[val])
                return " ".join(res)

            crores = n // 10000000
            n %= 10000000
            lakhs = n // 100000
            n %= 100000
            thousands = n // 1000
            n %= 1000
            rem = n

            parts = []
            if crores > 0:
                parts.append(convert_below_thousand(crores) + " Crore")
            if lakhs > 0:
                parts.append(convert_below_thousand(lakhs) + " Lakh")
            if thousands > 0:
                parts.append(convert_below_thousand(thousands) + " Thousand")
            if rem > 0:
                parts.append(convert_below_thousand(rem))

            return " ".join(parts).strip() + " Rupees Only"
        except Exception:
            return ""

    @property
    def is_pending(self):
        return self.status == 'PENDING'

    @property
    def is_approved(self):
        return self.status == 'APPROVED'

    @property
    def is_rejected(self):
        return self.status == 'REJECTED'

    @property
    def is_collected(self):
        return self.status == 'COLLECTED'

    @property
    def status_badge_class(self):
        mapping = {
            'PENDING': 'bg-warning text-dark',
            'APPROVED': 'bg-success text-white',
            'REJECTED': 'bg-danger text-white',
            'COLLECTED': 'bg-primary text-white',
            'EXPIRED': 'bg-secondary text-white'
        }
        return mapping.get(self.status, 'bg-secondary text-white')

    @property
    def branch_details(self):
        return self.BRANCHES.get(self.branch_code, {
            'name': self.branch_name,
            'ifsc': self.ifsc_code,
            'address': 'SmartBank Branch',
            'phone': '1800-419-0123'
        })

    def to_dict(self):
        return {
            'id': self.id,
            'token_number': self.token_number,
            'customer_name': self.customer.full_name if self.customer else None,
            'account_holder_name': self.account_holder_name or (self.customer.full_name if self.customer else None),
            'account_number': self.account.account_number if self.account else None,
            'branch_code': self.branch_code,
            'branch_name': self.branch_name,
            'ifsc_code': self.ifsc_code,
            'amount': float(self.amount),
            'amount_words': self.amount_words,
            'visit_date': self.visit_date.strftime('%Y-%m-%d') if self.visit_date else None,
            'time_slot': self.time_slot,
            'purpose': self.purpose,
            'denomination_preference': self.denomination_preference,
            'status': self.status,
            'priority_counter': self.priority_counter,
            'manager_remarks': self.manager_remarks,
            'approved_at': self.approved_at.strftime('%Y-%m-%d %H:%M:%S') if self.approved_at else None,
            'collected_at': self.collected_at.strftime('%Y-%m-%d %H:%M:%S') if self.collected_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<BranchCashRequest {self.token_number} - {self.branch_code} ₹{self.amount} [{self.status}]>"
