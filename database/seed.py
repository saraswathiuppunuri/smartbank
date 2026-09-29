import sys
import os
from decimal import Decimal
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, User, Customer, Account, Transaction, Beneficiary, Notification, Card

def seed_database():
    """Seeds the database with realistic demo data for presentation and testing."""
    app = create_app()
    with app.app_context():
        print("Ensuring database tables exist...")
        db.create_all()

        # Check if already seeded
        if User.query.filter_by(username='admin').first():
            print("Database already contains seed data. Skipping seed process.")
            return

        print("Seeding administrative and demo accounts...")

        # 1. Admin User
        admin_user = User(
            username='admin',
            email='admin@smartbank.com',
            role='admin',
            is_active=True
        )
        admin_user.set_password('Admin@1234')
        db.session.add(admin_user)
        db.session.flush()

        admin_notif = Notification(
            user_id=admin_user.id,
            title='System Operational',
            message='SmartBank Core Banking Engine initialized and operational.',
            type='SUCCESS'
        )
        db.session.add(admin_notif)

        # 2. Customer 1: Rahul Sharma
        user_rahul = User(
            username='rahul_sharma',
            email='rahul.sharma@example.com',
            role='customer',
            is_active=True
        )
        user_rahul.set_password('Password@123')
        db.session.add(user_rahul)
        db.session.flush()

        cust_rahul = Customer(
            user_id=user_rahul.id,
            customer_code='CUST-100201',
            first_name='Rahul',
            last_name='Sharma',
            phone='+919876543210',
            address='Flat 402, Green Valley Heights, MG Road',
            city='Bengaluru',
            state='Karnataka',
            pincode='560001',
            kyc_status='VERIFIED'
        )
        db.session.add(cust_rahul)
        db.session.flush()

        acc_rahul_savings = Account(
            customer_id=cust_rahul.id,
            account_number='100182749102',
            account_type='Savings',
            balance=Decimal('45500.00'),
            status='ACTIVE'
        )
        acc_rahul_salary = Account(
            customer_id=cust_rahul.id,
            account_number='100192847193',
            account_type='Salary',
            balance=Decimal('120000.00'),
            status='ACTIVE'
        )
        db.session.add_all([acc_rahul_savings, acc_rahul_salary])
        db.session.flush()

        # 3. Customer 2: Priya Patel
        user_priya = User(
            username='priya_patel',
            email='priya.patel@example.com',
            role='customer',
            is_active=True
        )
        user_priya.set_password('Password@123')
        db.session.add(user_priya)
        db.session.flush()

        cust_priya = Customer(
            user_id=user_priya.id,
            customer_code='CUST-100202',
            first_name='Priya',
            last_name='Patel',
            phone='+919812345678',
            address='12 Silver Oak Enclave, SG Highway',
            city='Ahmedabad',
            state='Gujarat',
            pincode='380015',
            kyc_status='VERIFIED'
        )
        db.session.add(cust_priya)
        db.session.flush()

        acc_priya_savings = Account(
            customer_id=cust_priya.id,
            account_number='100173829104',
            account_type='Savings',
            balance=Decimal('28450.00'),
            status='ACTIVE'
        )
        db.session.add(acc_priya_savings)
        db.session.flush()

        # 4. Customer 3: Amit Verma
        user_amit = User(
            username='amit_verma',
            email='amit.verma@example.com',
            role='customer',
            is_active=True
        )
        user_amit.set_password('Password@123')
        db.session.add(user_amit)
        db.session.flush()

        cust_amit = Customer(
            user_id=user_amit.id,
            customer_code='CUST-100203',
            first_name='Amit',
            last_name='Verma',
            phone='+919955443322',
            address='74 Connaught Place, Block C',
            city='New Delhi',
            state='Delhi',
            pincode='110001',
            kyc_status='VERIFIED'
        )
        db.session.add(cust_amit)
        db.session.flush()

        acc_amit_current = Account(
            customer_id=cust_amit.id,
            account_number='100164829105',
            account_type='Current',
            balance=Decimal('85000.00'),
            status='ACTIVE'
        )
        db.session.add(acc_amit_current)
        db.session.flush()

        # 5. Beneficiaries
        ben1 = Beneficiary(
            customer_id=cust_rahul.id,
            name='Priya Patel',
            account_number='100173829104',
            bank_name='SmartBank',
            ifsc_code='SMRT0001001',
            email='priya.patel@example.com'
        )
        ben2 = Beneficiary(
            customer_id=cust_rahul.id,
            name='Amit Verma',
            account_number='100164829105',
            bank_name='SmartBank',
            ifsc_code='SMRT0001001',
            email='amit.verma@example.com'
        )
        ben3 = Beneficiary(
            customer_id=cust_priya.id,
            name='Rahul Sharma',
            account_number='100182749102',
            bank_name='SmartBank',
            ifsc_code='SMRT0001001',
            email='rahul.sharma@example.com'
        )
        db.session.add_all([ben1, ben2, ben3])

        # 6. Historical Transactions
        now = datetime.utcnow()

        txns = [
            # Rahul opening deposits
            Transaction(
                transaction_ref='DEP2026090100101',
                account_id=acc_rahul_savings.id,
                transaction_type='DEPOSIT',
                amount=Decimal('50000.00'),
                balance_after=Decimal('50000.00'),
                description='Initial Account Opening Deposit',
                status='COMPLETED',
                created_at=now - timedelta(days=25)
            ),
            Transaction(
                transaction_ref='DEP2026090100102',
                account_id=acc_rahul_salary.id,
                transaction_type='DEPOSIT',
                amount=Decimal('120000.00'),
                balance_after=Decimal('120000.00'),
                description='Monthly Corporate Salary Credit',
                status='COMPLETED',
                created_at=now - timedelta(days=20)
            ),
            Transaction(
                transaction_ref='WTH2026090500201',
                account_id=acc_rahul_savings.id,
                transaction_type='WITHDRAWAL',
                amount=Decimal('5000.00'),
                balance_after=Decimal('45000.00'),
                description='ATM Cash Withdrawal - MG Road',
                status='COMPLETED',
                created_at=now - timedelta(days=15)
            ),
            # Transfer Rahul to Priya
            Transaction(
                transaction_ref='TRF2026091000301',
                account_id=acc_rahul_savings.id,
                transaction_type='TRANSFER_SENT',
                amount=Decimal('5000.00'),
                balance_after=Decimal('40000.00'),
                recipient_account='100173829104',
                description='Transfer to Priya Patel: Shared Apartment Rent',
                status='COMPLETED',
                created_at=now - timedelta(days=10)
            ),
            Transaction(
                transaction_ref='TRF2026091000301-R',
                account_id=acc_priya_savings.id,
                transaction_type='TRANSFER_RECEIVED',
                amount=Decimal('5000.00'),
                balance_after=Decimal('25000.00'),
                recipient_account='100182749102',
                description='Transfer from Rahul Sharma: Shared Apartment Rent',
                status='COMPLETED',
                created_at=now - timedelta(days=10)
            ),
            # Priya deposit
            Transaction(
                transaction_ref='DEP2026090200103',
                account_id=acc_priya_savings.id,
                transaction_type='DEPOSIT',
                amount=Decimal('20000.00'),
                balance_after=Decimal('20000.00'),
                description='Cash Deposit at Branch Counter',
                status='COMPLETED',
                created_at=now - timedelta(days=22)
            ),
            # Transfer Priya to Rahul
            Transaction(
                transaction_ref='TRF2026091800401',
                account_id=acc_priya_savings.id,
                transaction_type='TRANSFER_SENT',
                amount=Decimal('1550.00'),
                balance_after=Decimal('28450.00'),
                recipient_account='100182749102',
                description='Transfer to Rahul Sharma: Grocery split',
                status='COMPLETED',
                created_at=now - timedelta(days=5)
            ),
            Transaction(
                transaction_ref='TRF2026091800401-R',
                account_id=acc_rahul_savings.id,
                transaction_type='TRANSFER_RECEIVED',
                amount=Decimal('1550.00'),
                balance_after=Decimal('41550.00'),
                recipient_account='100173829104',
                description='Transfer from Priya Patel: Grocery split',
                status='COMPLETED',
                created_at=now - timedelta(days=5)
            ),
            # Amit opening deposit
            Transaction(
                transaction_ref='DEP2026090300104',
                account_id=acc_amit_current.id,
                transaction_type='DEPOSIT',
                amount=Decimal('85000.00'),
                balance_after=Decimal('85000.00'),
                description='Business Current Account Capital Deposit',
                status='COMPLETED',
                created_at=now - timedelta(days=18)
            ),
            # Recent deposit to Rahul savings
            Transaction(
                transaction_ref='DEP2026092500501',
                account_id=acc_rahul_savings.id,
                transaction_type='DEPOSIT',
                amount=Decimal('3950.00'),
                balance_after=Decimal('45500.00'),
                description='Online UPI Direct Credit',
                status='COMPLETED',
                created_at=now - timedelta(days=1)
            ),
        ]
        db.session.add_all(txns)

        # 7. Notifications
        notif_rahul1 = Notification(
            user_id=user_rahul.id,
            title='Welcome to SmartBank!',
            message='Your SmartBank Savings Account (100182749102) has been activated.',
            type='SUCCESS',
            is_read=True,
            created_at=now - timedelta(days=25)
        )
        notif_rahul2 = Notification(
            user_id=user_rahul.id,
            title='Transfer Sent',
            message='₹5,000.00 transferred to Priya Patel (100173829104). Ref: TRF2026091000301.',
            type='INFO',
            is_read=True,
            created_at=now - timedelta(days=10)
        )
        notif_rahul3 = Notification(
            user_id=user_rahul.id,
            title='Transfer Received',
            message='You received ₹1,550.00 from Priya Patel into account 100182749102.',
            type='SUCCESS',
            is_read=False,
            created_at=now - timedelta(days=5)
        )
        notif_priya1 = Notification(
            user_id=user_priya.id,
            title='Welcome to SmartBank!',
            message='Your account 100173829104 is active.',
            type='SUCCESS',
            is_read=True,
            created_at=now - timedelta(days=22)
        )
        db.session.add_all([notif_rahul1, notif_rahul2, notif_rahul3, notif_priya1])

        # 8. Debit Cards
        card_rahul_visa = Card(
            account_id=acc_rahul_savings.id,
            card_number='4532891023456789',
            card_network='VISA',
            card_type='DEBIT',
            card_holder_name='RAHUL SHARMA',
            cvv='842',
            expiry_month=12,
            expiry_year=2029,
            daily_limit=Decimal('50000.00'),
            status='ACTIVE',
            is_online_enabled=True,
            is_contactless_enabled=True,
            is_international_enabled=False
        )
        card_rahul_visa.set_pin('1234')

        card_rahul_mc = Card(
            account_id=acc_rahul_salary.id,
            card_number='5421987654321098',
            card_network='MASTERCARD',
            card_type='DEBIT',
            card_holder_name='RAHUL SHARMA',
            cvv='319',
            expiry_month=8,
            expiry_year=2030,
            daily_limit=Decimal('100000.00'),
            status='ACTIVE',
            is_online_enabled=True,
            is_contactless_enabled=True,
            is_international_enabled=True
        )
        card_rahul_mc.set_pin('4321')

        card_priya_rupay = Card(
            account_id=acc_priya_savings.id,
            card_number='6071829102938475',
            card_network='RUPAY',
            card_type='DEBIT',
            card_holder_name='PRIYA PATEL',
            cvv='675',
            expiry_month=5,
            expiry_year=2028,
            daily_limit=Decimal('25000.00'),
            status='ACTIVE',
            is_online_enabled=True,
            is_contactless_enabled=False,
            is_international_enabled=False
        )
        card_priya_rupay.set_pin('1234')

        card_amit_visa = Card(
            account_id=acc_amit_current.id,
            card_number='4716901234567890',
            card_network='VISA',
            card_type='DEBIT',
            card_holder_name='AMIT VERMA',
            cvv='528',
            expiry_month=11,
            expiry_year=2029,
            daily_limit=Decimal('75000.00'),
            status='ACTIVE',
            is_online_enabled=True,
            is_contactless_enabled=True,
            is_international_enabled=True
        )
        card_amit_visa.set_pin('9999')

        db.session.add_all([card_rahul_visa, card_rahul_mc, card_priya_rupay, card_amit_visa])

        db.session.commit()
        print("Database seed completed successfully!")
        print("Demo Accounts:")
        print("  - Admin:    admin / Admin@1234")
        print("  - Customer: rahul_sharma / Password@123 (Accounts: 100182749102, 100192847193)")
        print("  - Customer: priya_patel / Password@123 (Account: 100173829104)")
        print("  - Customer: amit_verma / Password@123 (Account: 100164829105)")
        print("Demo Cards:")
        print("  - Visa Platinum:       4532891023456789 | CVV: 842 | Exp: 12/29 | PIN: 1234 (Rahul)")
        print("  - Mastercard Titanium: 5421987654321098 | CVV: 319 | Exp: 08/30 | PIN: 4321 (Rahul)")
        print("  - RuPay Platinum:      6071829102938475 | CVV: 675 | Exp: 05/28 | PIN: 1234 (Priya)")
        print("  - Visa Business:       4716901234567890 | CVV: 528 | Exp: 11/29 | PIN: 9999 (Amit)")

if __name__ == '__main__':
    seed_database()
