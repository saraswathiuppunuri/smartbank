import sys
import argparse
from decimal import Decimal
from app import create_app
from models import db, User, Customer, Account, Transaction, Notification

def create_user_cli(username, email, password, role='customer', first_name='', last_name='', phone='', account_type='Savings', initial_deposit=1000.0):
    """Programmatically create a new User, Customer profile, and Bank Account."""
    app = create_app()
    with app.app_context():
        # Check existing
        if User.query.filter_by(username=username).first():
            print(f"Error: Username '{username}' already exists.")
            return False
        if User.query.filter_by(email=email).first():
            print(f"Error: Email '{email}' already registered.")
            return False

        try:
            # 1. Create User
            user = User(
                username=username,
                email=email,
                role=role,
                is_active=True
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            if role == 'customer':
                # 2. Create Customer Profile
                cust_code = Customer.generate_customer_code()
                customer = Customer(
                    user_id=user.id,
                    customer_code=cust_code,
                    first_name=first_name or username.capitalize(),
                    last_name=last_name or 'User',
                    phone=phone or '9876543210',
                    kyc_status='VERIFIED'
                )
                db.session.add(customer)
                db.session.flush()

                # 3. Create Bank Account
                acc_num = Account.generate_account_number()
                deposit_amt = Decimal(str(initial_deposit))
                account = Account(
                    customer_id=customer.id,
                    account_number=acc_num,
                    account_type=account_type,
                    balance=deposit_amt,
                    status='ACTIVE'
                )
                db.session.add(account)
                db.session.flush()

                # 4. Opening Deposit Transaction Record
                if deposit_amt > 0:
                    txn = Transaction(
                        transaction_ref=Transaction.generate_txn_ref(),
                        account_id=account.id,
                        transaction_type='DEPOSIT',
                        amount=deposit_amt,
                        balance_after=deposit_amt,
                        description='Opening Balance Deposit',
                        status='COMPLETED'
                    )
                    db.session.add(txn)

                # 5. Welcome Notification
                notif = Notification(
                    user_id=user.id,
                    title='Welcome to SmartBank!',
                    message=f"Your account {acc_num} has been successfully provisioned.",
                    type='SUCCESS'
                )
                db.session.add(notif)

            db.session.commit()

            print("\nSUCCESS: User created successfully!")
            print(f"  - Username    : {user.username}")
            print(f"  - Email       : {user.email}")
            print(f"  - Role        : {user.role}")
            if role == 'customer':
                print(f"  - Customer ID : {cust_code}")
                print(f"  - Account No  : {acc_num} ({account_type})")
                print(f"  - Balance     : INR {deposit_amt:,.2f}")
            return True

        except Exception as e:
            db.session.rollback()
            print(f"Failed to create user: {e}")
            return False

def interactive_mode():
    print("=" * 55)
    print("        SmartBank User Creation Utility")
    print("=" * 55)
    role_choice = input("Select Role [1: Customer, 2: Admin] (Default: 1): ").strip()
    role = 'admin' if role_choice == '2' else 'customer'

    username = input("Username: ").strip()
    email = input("Email address: ").strip()
    password = input("Password: ").strip()

    if not username or not email or not password:
        print("Error: Username, Email, and Password cannot be empty.")
        return

    if role == 'customer':
        first_name = input("First Name: ").strip() or username.capitalize()
        last_name = input("Last Name: ").strip() or "User"
        phone = input("Phone Number (+91...): ").strip() or "9876543210"
        
        print("\nAccount Types: 1. Savings, 2. Current, 3. Salary")
        acc_type_choice = input("Choose Account Type (Default: 1): ").strip()
        acc_types = {'1': 'Savings', '2': 'Current', '3': 'Salary'}
        account_type = acc_types.get(acc_type_choice, 'Savings')

        deposit_str = input("Initial Opening Deposit in ₹ (Default: 1000): ").strip() or "1000"
        try:
            deposit = float(deposit_str)
        except ValueError:
            deposit = 1000.0

        create_user_cli(username, email, password, role, first_name, last_name, phone, account_type, deposit)
    else:
        create_user_cli(username, email, password, role)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Create SmartBank users via command line.")
    parser.add_argument('--username', help="User login username")
    parser.add_argument('--email', help="User email address")
    parser.add_argument('--password', help="User password")
    parser.add_argument('--role', choices=['customer', 'admin'], default='customer', help="Role: customer or admin")
    parser.add_argument('--first_name', default='', help="First name (for customer)")
    parser.add_argument('--last_name', default='', help="Last name (for customer)")
    parser.add_argument('--phone', default='', help="Phone number (for customer)")
    parser.add_argument('--account_type', choices=['Savings', 'Current', 'Salary'], default='Savings', help="Bank account type")
    parser.add_argument('--deposit', type=float, default=1000.0, help="Initial opening deposit amount")

    args = parser.parse_args()

    if args.username and args.email and args.password:
        create_user_cli(
            username=args.username,
            email=args.email,
            password=args.password,
            role=args.role,
            first_name=args.first_name,
            last_name=args.last_name,
            phone=args.phone,
            account_type=args.account_type,
            initial_deposit=args.deposit
        )
    else:
        interactive_mode()
