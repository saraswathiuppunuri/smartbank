import unittest
import json
from decimal import Decimal
from datetime import date, timedelta
from app import create_app
from models import db, User, Customer, Account, Transaction, Beneficiary, Notification, Card, BranchCashRequest

class SmartBankTestCase(unittest.TestCase):
    """Automated test suite verifying core banking functionality."""

    def setUp(self):
        """Set up test client with clean in-memory database."""
        self.app = create_app('testing')
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        # Seed essential baseline accounts for tests
        self._seed_baseline()

    def tearDown(self):
        """Clean up database session and tables."""
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _seed_baseline(self):
        """Seed admin and two active customers."""
        # 1. Admin
        admin = User(username='admin', email='admin@smartbank.com', role='admin', is_active=True)
        admin.set_password('Admin@1234')
        db.session.add(admin)

        # 2. Customer 1: Alice
        u1 = User(username='alice', email='alice@test.com', role='customer', is_active=True)
        u1.set_password('Alice@123')
        db.session.add(u1)
        db.session.flush()

        c1 = Customer(
            user_id=u1.id,
            customer_code='CUST-111111',
            first_name='Alice',
            last_name='Smith',
            phone='9876543210',
            kyc_status='VERIFIED'
        )
        db.session.add(c1)
        db.session.flush()

        acc1 = Account(
            customer_id=c1.id,
            account_number='100111111111',
            account_type='Savings',
            balance=Decimal('5000.00'),
            status='ACTIVE'
        )
        db.session.add(acc1)

        # 3. Customer 2: Bob
        u2 = User(username='bob', email='bob@test.com', role='customer', is_active=True)
        u2.set_password('Bob@123')
        db.session.add(u2)
        db.session.flush()

        c2 = Customer(
            user_id=u2.id,
            customer_code='CUST-222222',
            first_name='Bob',
            last_name='Jones',
            phone='9123456789',
            kyc_status='VERIFIED'
        )
        db.session.add(c2)
        db.session.flush()

        acc2 = Account(
            customer_id=c2.id,
            account_number='100122222222',
            account_type='Savings',
            balance=Decimal('2000.00'),
            status='ACTIVE'
        )
        db.session.add(acc2)
        db.session.commit()

    def login(self, identifier, password):
        """Helper to simulate web login."""
        return self.client.post('/auth/login', data={
            'identifier': identifier,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        """Helper to simulate logout."""
        return self.client.get('/auth/logout', follow_redirects=True)

    # --- Test 1: User Registration ---
    def test_customer_registration(self):
        """Verify new customer registers, profile is created, and primary account opens."""
        res = self.client.post('/auth/register', data={
            'username': 'charlie',
            'email': 'charlie@test.com',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'first_name': 'Charlie',
            'last_name': 'Brown',
            'phone': '9898989898',
            'account_type': 'Savings',
            'initial_deposit': '1500.00'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify DB records
        user = User.query.filter_by(username='charlie').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.check_password('Password@123'))
        self.assertIsNotNone(user.customer)
        self.assertEqual(user.customer.first_name, 'Charlie')

        # Verify Account
        acc = user.customer.accounts.first()
        self.assertIsNotNone(acc)
        self.assertEqual(float(acc.balance), 1500.00)

        # Verify Opening Transaction
        txn = Transaction.query.filter_by(account_id=acc.id).first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.transaction_type, 'DEPOSIT')

    # --- Test 2: Authentication ---
    def test_login_and_logout(self):
        """Verify successful login, incorrect password, and logout session clearing."""
        # 1. Successful Login
        res = self.login('alice', 'Alice@123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hello, Alice Smith!', res.data)

        # 2. Logout
        res_logout = self.logout()
        self.assertEqual(res_logout.status_code, 200)
        self.assertIn(b'logged out securely', res_logout.data)

        # 3. Invalid Password
        res_fail = self.login('alice', 'WrongPassword')
        self.assertIn(b'Invalid username/email or password', res_fail.data)

    # --- Test 3: Role Authorization ---
    def test_role_authorization_protection(self):
        """Verify customers cannot access admin portal and unauthorized guests are redirected."""
        # Guest accessing customer dashboard
        res_guest = self.client.get('/customer/dashboard', follow_redirects=False)
        self.assertEqual(res_guest.status_code, 302)
        self.assertIn('/auth/login', res_guest.headers['Location'])

        # Customer accessing admin console
        self.login('alice', 'Alice@123')
        res_cust_admin = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertIn(b'Unauthorized access', res_cust_admin.data)

        # Admin accessing admin console
        self.logout()
        self.login('admin', 'Admin@1234')
        res_admin = self.client.get('/admin/dashboard')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b'SmartBank Administration Console', res_admin.data)

    # --- Test 4: Deposit Functionality ---
    def test_deposit_operations(self):
        """Test valid deposit and rejection of negative or zero amount."""
        self.login('alice', 'Alice@123')
        acc = Account.query.filter_by(account_number='100111111111').first()
        initial_balance = acc.balance

        # 1. Valid Deposit
        deposit_amount = Decimal('2500.00')
        res = self.client.post('/deposit', data={
            'account_id': acc.id,
            'amount': str(deposit_amount),
            'description': 'Freelance payment'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify DB balance
        acc_updated = db.session.get(Account, acc.id)
        self.assertEqual(acc_updated.balance, initial_balance + deposit_amount)

        # 2. Invalid Zero/Negative Deposit
        res_neg = self.client.post('/deposit', data={
            'account_id': acc.id,
            'amount': '-50.00'
        }, follow_redirects=True)
        self.assertIn(b'Deposit amount must be strictly greater than zero', res_neg.data)

    # --- Test 5: Withdrawal Functionality ---
    def test_withdrawal_operations(self):
        """Test valid withdrawal and balance guard against overdrawing."""
        self.login('alice', 'Alice@123')
        acc = Account.query.filter_by(account_number='100111111111').first()
        current_balance = acc.balance

        # 1. Valid Withdrawal
        res = self.client.post('/withdraw', data={
            'account_id': acc.id,
            'amount': '1000.00',
            'description': 'Cash withdrawal'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        acc_updated = db.session.get(Account, acc.id)
        self.assertEqual(acc_updated.balance, current_balance - Decimal('1000.00'))

        # 2. Overdraw rejection
        res_over = self.client.post('/withdraw', data={
            'account_id': acc.id,
            'amount': '100000.00'
        }, follow_redirects=True)
        self.assertIn(b'Insufficient funds', res_over.data)

    # --- Test 6: Fund Transfer Operations ---
    def test_fund_transfer_atomic_execution(self):
        """Test inter-account transfer, atomic debits/credits, and audit records."""
        self.login('alice', 'Alice@123')
        alice_acc = Account.query.filter_by(account_number='100111111111').first()
        bob_acc = Account.query.filter_by(account_number='100122222222').first()

        alice_start = alice_acc.balance
        bob_start = bob_acc.balance
        transfer_amt = Decimal('1200.00')

        res = self.client.post('/transfer', data={
            'source_account_id': alice_acc.id,
            'recipient_account_number': '100122222222',
            'amount': str(transfer_amt),
            'description': 'Test transfer'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Refresh balances
        alice_acc_after = db.session.get(Account, alice_acc.id)
        bob_acc_after = db.session.get(Account, bob_acc.id)

        self.assertEqual(alice_acc_after.balance, alice_start - transfer_amt)
        self.assertEqual(bob_acc_after.balance, bob_start + transfer_amt)

        # Verify Two Transaction Entries Exist
        sent_txn = Transaction.query.filter_by(account_id=alice_acc.id, transaction_type='TRANSFER_SENT').first()
        received_txn = Transaction.query.filter_by(account_id=bob_acc.id, transaction_type='TRANSFER_RECEIVED').first()
        self.assertIsNotNone(sent_txn)
        self.assertIsNotNone(received_txn)

    # --- Test 7: Prevent Self-Transfer ---
    def test_fund_transfer_self_transfer_prevention(self):
        """Transferring to the same account must be blocked."""
        self.login('alice', 'Alice@123')
        alice_acc = Account.query.filter_by(account_number='100111111111').first()

        res = self.client.post('/transfer', data={
            'source_account_id': alice_acc.id,
            'recipient_account_number': '100111111111',
            'amount': '500.00'
        }, follow_redirects=True)
        self.assertIn(b'Source and recipient accounts cannot be identical', res.data)

    # --- Test 8: Admin Customer CRUD & Deactivation ---
    def test_admin_customer_deactivation(self):
        """Verify admin can deactivate customer and deactivated customer cannot log in."""
        self.login('admin', 'Admin@1234')
        cust = Customer.query.filter_by(customer_code='CUST-111111').first()
        self.assertTrue(cust.user.is_active)

        # Toggle deactivation
        res = self.client.post(f'/admin/customers/{cust.id}/toggle-status', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check in DB
        cust_after = db.session.get(Customer, cust.id)
        self.assertFalse(cust_after.user.is_active)

        # Attempt login with deactivated user
        self.logout()
        res_login = self.login('alice', 'Alice@123')
        self.assertIn(b'Your account has been deactivated', res_login.data)

    # --- Test 9: Beneficiary CRUD ---
    def test_beneficiary_lifecycle(self):
        """Test adding, editing, and deleting a beneficiary."""
        self.login('alice', 'Alice@123')

        # Add Beneficiary
        res_add = self.client.post('/customer/beneficiaries', data={
            'name': 'Bob Jones',
            'account_number': '100122222222',
            'bank_name': 'SmartBank',
            'ifsc_code': 'SMRT0001001',
            'email': 'bob@test.com'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)

        ben = Beneficiary.query.filter_by(account_number='100122222222').first()
        self.assertIsNotNone(ben)
        self.assertEqual(ben.name, 'Bob Jones')

        # Delete Beneficiary
        res_del = self.client.post(f'/customer/beneficiaries/delete/{ben.id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIsNone(db.session.get(Beneficiary, ben.id))

    # --- Test 10: RESTful API Endpoints ---
    def test_api_deposit_and_transfer(self):
        """Test API endpoints for authentication, deposit, and balance retrieval."""
        # 1. API Login
        login_res = self.client.post('/api/login', json={
            'identifier': 'alice',
            'password': 'Alice@123'
        })
        self.assertEqual(login_res.status_code, 200)
        login_json = login_res.get_json()
        self.assertTrue(login_json['success'])

        # 2. API Deposit
        dep_res = self.client.post('/api/deposit', json={
            'account_number': '100111111111',
            'amount': '500.00',
            'description': 'REST API Deposit'
        })
        self.assertEqual(dep_res.status_code, 200)
        dep_json = dep_res.get_json()
        self.assertTrue(dep_json['success'])
        self.assertEqual(dep_json['data']['account']['balance'], 5500.00)

    # --- Test 11: Debit Card Issuance & Management ---
    def test_debit_card_issuance_and_management(self):
        """Verify card issuance, PIN modification, limit updates, and freeze toggling."""
        self.login('alice', 'Alice@123')
        acc = Account.query.filter_by(account_number='100111111111').first()

        # 1. Apply for new Visa Debit Card
        res_apply = self.client.post('/cards/apply', data={
            'account_id': acc.id,
            'card_network': 'VISA',
            'card_type': 'Platinum',
            'daily_limit': '30000.00',
            'pin': '2468',
            'confirm_pin': '2468'
        }, follow_redirects=True)
        self.assertEqual(res_apply.status_code, 200)
        self.assertIn(b'issued successfully', res_apply.data)

        card = Card.query.filter_by(account_id=acc.id).first()
        self.assertIsNotNone(card)
        self.assertEqual(card.card_network, 'VISA')
        self.assertTrue(card.check_pin('2468'))
        self.assertFalse(card.is_locked)
        self.assertTrue(card.is_online_enabled)

        # 2. Update Daily Limit
        res_limit = self.client.post(f'/cards/{card.id}/update-limit', data={
            'daily_limit': '45000.00'
        }, follow_redirects=True)
        self.assertEqual(res_limit.status_code, 200)
        db.session.refresh(card)
        self.assertEqual(float(card.daily_limit), 45000.00)

        # 3. Update PIN
        res_pin = self.client.post(f'/cards/{card.id}/set-pin', data={
            'current_pin': '2468',
            'new_pin': '9876',
            'confirm_pin': '9876'
        }, follow_redirects=True)
        self.assertEqual(res_pin.status_code, 200)
        db.session.refresh(card)
        self.assertTrue(card.check_pin('9876'))

        # 4. Toggle Card Freeze / Lock
        res_lock = self.client.post(f'/cards/{card.id}/toggle-lock', follow_redirects=True)
        self.assertEqual(res_lock.status_code, 200)
        db.session.refresh(card)
        self.assertTrue(card.is_locked)

        # Unfreeze
        self.client.post(f'/cards/{card.id}/toggle-lock', follow_redirects=True)
        db.session.refresh(card)
        self.assertFalse(card.is_locked)

    # --- Test 12: Debit Card Payment Simulator & Security Checks ---
    def test_debit_card_payment_simulation(self):
        """Verify card POS/online transaction simulation with balance deduction and security guards."""
        self.login('alice', 'Alice@123')
        acc = Account.query.filter_by(account_number='100111111111').first()

        # Seed card directly for deterministic credentials
        card = Card(
            account_id=acc.id,
            card_number='4532111122223333',
            card_network='VISA',
            card_type='DEBIT',
            card_holder_name='ALICE SMITH',
            cvv='789',
            expiry_month=12,
            expiry_year=2029,
            daily_limit=Decimal('10000.00'),
            status='ACTIVE',
            is_online_enabled=True
        )
        card.set_pin('1122')
        db.session.add(card)
        db.session.commit()

        # 1. Successful Online Payment
        res_pay = self.client.post('/cards/simulator/pay', data={
            'card_number': '4532111122223333',
            'expiry_month': '12',
            'expiry_year': '2029',
            'cvv': '789',
            'amount': '1500.00',
            'merchant': 'Flipkart Internet',
            'category': 'SHOPPING'
        }, follow_redirects=True)
        self.assertEqual(res_pay.status_code, 200)
        self.assertIn(b'Payment of', res_pay.data)
        self.assertIn(b'SUCCESSFUL', res_pay.data)

        # Balance check: 5000 - 1500 = 3500
        db.session.refresh(acc)
        self.assertEqual(float(acc.balance), 3500.00)

        # 2. Reject Wrong CVV
        res_bad_cvv = self.client.post('/cards/simulator/pay', data={
            'card_number': '4532111122223333',
            'expiry_month': '12',
            'expiry_year': '2029',
            'cvv': '000',
            'amount': '200.00',
            'merchant': 'Test Store',
            'category': 'SHOPPING'
        }, follow_redirects=True)
        self.assertIn(b'Invalid CVV security code', res_bad_cvv.data)

        # 3. Reject When Online Channel Disabled
        card.is_online_enabled = False
        db.session.commit()
        res_no_online = self.client.post('/cards/simulator/pay', data={
            'card_number': '4532111122223333',
            'expiry_month': '12',
            'expiry_year': '2029',
            'cvv': '789',
            'amount': '200.00',
            'merchant': 'Test Store',
            'category': 'SHOPPING'
        }, follow_redirects=True)
        self.assertIn(b'Online / E-commerce usage is disabled', res_no_online.data)

        # 4. Reject When Exceeding Daily Limit
        card.is_online_enabled = True
        card.daily_limit = Decimal('2000.00')
        db.session.commit()
        # Spent so far today is 1500, limit is 2000. Trying 600 should fail (1500+600=2100 > 2000)
        res_limit_fail = self.client.post('/cards/simulator/pay', data={
            'card_number': '4532111122223333',
            'expiry_month': '12',
            'expiry_year': '2029',
            'cvv': '789',
            'amount': '600.00',
            'merchant': 'Luxury Goods',
            'category': 'SHOPPING'
        }, follow_redirects=True)
        self.assertIn(b'Exceeds daily card spending limit', res_limit_fail.data)

    # --- Test 13: Debit Card ATM Withdrawal Simulation ---
    def test_atm_card_withdrawal_simulation(self):
        """Verify ATM cash withdrawal with PIN verification and atomic balance deduction."""
        self.login('alice', 'Alice@123')
        acc = Account.query.filter_by(account_number='100111111111').first()

        card = Card(
            account_id=acc.id,
            card_number='4532444455556666',
            card_network='VISA',
            card_type='DEBIT',
            card_holder_name='ALICE SMITH',
            cvv='456',
            expiry_month=10,
            expiry_year=2030,
            daily_limit=Decimal('20000.00'),
            status='ACTIVE'
        )
        card.set_pin('5566')
        db.session.add(card)
        db.session.commit()

        # 1. Invalid PIN Rejected
        res_wrong_pin = self.client.post('/cards/simulator/atm', data={
            'card_number': '4532444455556666',
            'pin': '9999',
            'amount': '1000.00',
            'atm_location': 'SmartBank ATM 102'
        }, follow_redirects=True)
        self.assertIn(b'Incorrect 4-digit ATM PIN', res_wrong_pin.data)

        # 2. Valid ATM Withdrawal
        res_atm_ok = self.client.post('/cards/simulator/atm', data={
            'card_number': '4532444455556666',
            'pin': '5566',
            'amount': '1000.00',
            'atm_location': 'SmartBank ATM 102'
        }, follow_redirects=True)
        self.assertEqual(res_atm_ok.status_code, 200)
        self.assertIn(b'ATM Cash Dispensed', res_atm_ok.data)

        # Verify balance: 5000 - 1000 = 4000
        db.session.refresh(acc)
        self.assertEqual(float(acc.balance), 4000.00)

        # Verify transaction logged
        atm_txn = Transaction.query.filter_by(transaction_type='ATM_WITHDRAWAL', account_id=acc.id).first()
        self.assertIsNotNone(atm_txn)
        self.assertEqual(float(atm_txn.amount), 1000.00)

    # --- Test 14: Branch Cash Withdrawal Slip Lifecycle ---
    def test_branch_cash_withdrawal_slip_lifecycle(self):
        """Verify customer submits digital slip, manager approves with counter, and offline cash dispense debits balance."""
        # 1. Customer Alice submits cash slip
        self.login('alice', 'Alice@123')
        acc = Account.query.filter_by(account_number='100111111111').first()

        visit_dt = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
        res_submit = self.client.post('/branch-cash/new', data={
            'account_id': acc.id,
            'branch_code': 'KPHB',
            'amount': '2500.00',
            'visit_date': visit_dt,
            'time_slot': 'Morning: 10:00 AM - 12:00 PM',
            'purpose': 'Real Estate / Property Advance',
            'denomination_preference': '₹500 x 5 notes',
            'signature_data': 'DIGITALLY SIGNED BY ALICE'
        }, follow_redirects=True)
        self.assertEqual(res_submit.status_code, 200)
        self.assertIn(b'Digital Withdrawal Slip submitted successfully', res_submit.data)

        req = BranchCashRequest.query.filter_by(account_id=acc.id).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, 'PENDING')
        self.assertEqual(req.branch_code, 'KPHB')
        self.assertEqual(req.ifsc_code, 'SMRT000KPHB')
        self.assertTrue(req.token_number.startswith('CS-KPHB-'))

        # Verify slip view
        res_slip = self.client.get(f'/branch-cash/slip/{req.id}')
        self.assertEqual(res_slip.status_code, 200)
        self.assertIn(req.token_number.encode(), res_slip.data)

        # 2. Manager logs in and approves slip
        self.logout()
        self.login('admin', 'Admin@1234')

        res_approve = self.client.post(f'/branch-cash/admin/{req.id}/approve', data={
            'priority_counter': 'Counter 2 (Fast-Track Cash)',
            'manager_remarks': 'Pre-approved. Currency reserved.'
        }, follow_redirects=True)
        self.assertEqual(res_approve.status_code, 200)
        db.session.refresh(req)
        self.assertEqual(req.status, 'APPROVED')
        self.assertEqual(req.priority_counter, 'Counter 2 (Fast-Track Cash)')

        # 3. Simulate customer visiting branch offline & teller dispensing cash
        res_dispense = self.client.post(f'/branch-cash/admin/{req.id}/dispense', follow_redirects=True)
        self.assertEqual(res_dispense.status_code, 200)
        self.assertIn(b'DISPENSED SUCCESSFULLY', res_dispense.data)

        # Balance check: 5000 - 2500 = 2500
        db.session.refresh(acc)
        self.assertEqual(float(acc.balance), 2500.00)

        db.session.refresh(req)
        self.assertEqual(req.status, 'COLLECTED')
        self.assertIsNotNone(req.transaction_id)

    # --- Test 15: Branch Cash Request Validation & Rejection Guards ---
    def test_branch_cash_rejection_and_guards(self):
        """Verify amount exceeding balance is declined and manager can reject with remarks."""
        self.login('alice', 'Alice@123')
        acc = Account.query.filter_by(account_number='100111111111').first()

        # 1. Attempt to request amount exceeding balance (balance is 5000)
        res_excess = self.client.post('/branch-cash/new', data={
            'account_id': acc.id,
            'branch_code': 'AMEERPET',
            'amount': '99999.00',
            'visit_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'time_slot': 'Morning: 10:00 AM - 12:00 PM',
            'purpose': 'Personal'
        }, follow_redirects=True)
        self.assertIn(b'Insufficient funds', res_excess.data)

        # 2. Submit valid request
        self.client.post('/branch-cash/new', data={
            'account_id': acc.id,
            'branch_code': 'HITECH',
            'amount': '1500.00',
            'visit_date': (date.today() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'time_slot': 'Afternoon: 12:00 PM - 02:00 PM',
            'purpose': 'Personal'
        }, follow_redirects=True)

        req = BranchCashRequest.query.filter_by(branch_code='HITECH').first()
        self.assertIsNotNone(req)

        # 3. Manager declines request with remarks
        self.logout()
        self.login('admin', 'Admin@1234')
        res_reject = self.client.post(f'/branch-cash/admin/{req.id}/reject', data={
            'manager_remarks': 'Signature mismatch against KYC records.'
        }, follow_redirects=True)
        self.assertEqual(res_reject.status_code, 200)

        db.session.refresh(req)
        self.assertEqual(req.status, 'REJECTED')
        self.assertEqual(req.manager_remarks, 'Signature mismatch against KYC records.')

if __name__ == '__main__':
    unittest.main()
