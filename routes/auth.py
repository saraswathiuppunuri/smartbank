import re
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, User, Customer, Account, Transaction, Notification
from routes.helpers import get_current_user

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticate user with session creation and role redirection."""
    # If already logged in, redirect to respective dashboard
    current_user = get_current_user()
    if current_user:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '').strip()
        remember = bool(request.form.get('remember'))

        if not identifier or not password:
            flash('Please provide both username/email and password.', 'danger')
            return render_template('auth/login.html', identifier=identifier)

        # Allow login by username or email
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user or not user.check_password(password):
            flash('Invalid username/email or password. Please try again.', 'danger')
            return render_template('auth/login.html', identifier=identifier)

        if not user.is_active:
            flash('Your account has been deactivated. Please contact SmartBank administration.', 'danger')
            return render_template('auth/login.html', identifier=identifier)

        # Set session details
        session.clear()
        session.permanent = remember
        session['user_id'] = user.id
        session['username'] = user.username
        session['email'] = user.email
        session['role'] = user.role

        if user.role == 'customer' and user.customer:
            session['customer_id'] = user.customer.id
            session['customer_name'] = user.customer.full_name
            session['customer_code'] = user.customer.customer_code

        flash(f'Welcome back, {user.username}!', 'success')

        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)

        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('customer.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register a new customer, customer profile, and primary bank account."""
    current_user = get_current_user()
    if current_user:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        account_type = request.form.get('account_type', 'Savings').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        initial_deposit_str = request.form.get('initial_deposit', '1000').strip()

        # Validations
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters long.')
        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            errors.append('Username can only contain letters, numbers, dots, underscores, and dashes.')
        if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errors.append('Please provide a valid email address.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if not first_name or not last_name:
            errors.append('First name and last name are required.')
        if not phone or not re.match(r'^\+?[0-9]{10,15}$', phone.replace(' ', '')):
            errors.append('Please enter a valid phone number (10-15 digits).')
        if account_type not in ['Savings', 'Current', 'Salary']:
            account_type = 'Savings'

        try:
            initial_deposit = Decimal(initial_deposit_str) if initial_deposit_str else Decimal('0.00')
            if initial_deposit < 0:
                errors.append('Initial deposit cannot be negative.')
        except Exception:
            errors.append('Invalid initial deposit amount.')
            initial_deposit = Decimal('0.00')

        # Check existing user
        if User.query.filter_by(username=username).first():
            errors.append(f"Username '{username}' is already registered.")
        if User.query.filter_by(email=email).first():
            errors.append(f"Email '{email}' is already registered.")

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/register.html', form_data=request.form)

        try:
            # 1. Create User
            new_user = User(
                username=username,
                email=email,
                role='customer',
                is_active=True
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()  # Flush to get user.id

            # 2. Create Customer Profile
            customer_code = Customer.generate_customer_code()
            new_customer = Customer(
                user_id=new_user.id,
                customer_code=customer_code,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                address=address,
                city=city,
                state=state,
                pincode=pincode,
                kyc_status='VERIFIED'
            )
            db.session.add(new_customer)
            db.session.flush()  # Flush to get customer.id

            # 3. Create Primary Bank Account
            account_number = Account.generate_account_number()
            new_account = Account(
                customer_id=new_customer.id,
                account_number=account_number,
                account_type=account_type,
                balance=initial_deposit,
                status='ACTIVE',
                currency='INR'
            )
            db.session.add(new_account)
            db.session.flush()

            # 4. If initial deposit, create transaction audit record
            if initial_deposit > 0:
                txn = Transaction(
                    transaction_ref=Transaction.generate_txn_ref(),
                    account_id=new_account.id,
                    transaction_type='DEPOSIT',
                    amount=initial_deposit,
                    balance_after=initial_deposit,
                    recipient_account=None,
                    description='Initial Account Opening Deposit',
                    status='COMPLETED'
                )
                db.session.add(txn)

            # 5. Welcome Notification
            welcome_notif = Notification(
                user_id=new_user.id,
                title='Welcome to SmartBank!',
                message=f"Congratulations {first_name}! Your {account_type} account ({account_number}) is active with initial balance ₹{initial_deposit:,.2f}.",
                type='SUCCESS'
            )
            db.session.add(welcome_notif)

            # Commit all operations atomically
            db.session.commit()

            flash(f"Account created successfully! Your customer ID is {customer_code} and account number is {account_number}. Please log in.", 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred during registration: {str(e)}", 'danger')
            return render_template('auth/register.html', form_data=request.form)

    return render_template('auth/register.html', form_data={})


@auth_bp.route('/logout')
def logout():
    """Clear session data and log out."""
    session.clear()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('auth.login'))
