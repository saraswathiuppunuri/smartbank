import re
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import db, User, Customer, Account, Transaction, Notification
from routes.helpers import login_required, admin_required, notify_user

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin Dashboard showing overall banking analytics and fast metrics."""
    total_customers = Customer.query.count()
    total_accounts = Account.query.count()
    active_accounts = Account.query.filter_by(status='ACTIVE').count()
    inactive_accounts = Account.query.filter(Account.status.in_(['INACTIVE', 'SUSPENDED'])).count()

    total_deposits = sum(
        float(t.amount) for t in Transaction.query.filter_by(transaction_type='DEPOSIT', status='COMPLETED').all()
    )
    total_withdrawals = sum(
        float(t.amount) for t in Transaction.query.filter_by(transaction_type='WITHDRAWAL', status='COMPLETED').all()
    )
    total_transfers = sum(
        float(t.amount) for t in Transaction.query.filter_by(transaction_type='TRANSFER_SENT', status='COMPLETED').all()
    )
    total_transactions = Transaction.query.count()

    # Recent activity
    recent_customers = Customer.query.order_by(Customer.created_at.desc()).limit(5).all()
    recent_transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        total_customers=total_customers,
        total_accounts=total_accounts,
        active_accounts=active_accounts,
        inactive_accounts=inactive_accounts,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        total_transfers=total_transfers,
        total_transactions=total_transactions,
        recent_customers=recent_customers,
        recent_transactions=recent_transactions
    )


@admin_bp.route('/customers', methods=['GET', 'POST'])
@login_required
@admin_required
def customers():
    """Admin Customer CRUD: List customers with search/filter, and Create new customer."""
    if request.method == 'POST':
        # Create Customer directly by Admin
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', 'Bank@1234')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        account_type = request.form.get('account_type', 'Savings')
        initial_deposit_str = request.form.get('initial_deposit', '1000').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()

        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errors.append('Valid email is required.')
        if not first_name or not last_name:
            errors.append('First and last name are required.')
        if not phone:
            errors.append('Phone number is required.')

        if User.query.filter_by(username=username).first():
            errors.append(f"Username '{username}' already exists.")
        if User.query.filter_by(email=email).first():
            errors.append(f"Email '{email}' already registered.")

        try:
            initial_deposit = Decimal(initial_deposit_str) if initial_deposit_str else Decimal('0.00')
            if initial_deposit < 0:
                errors.append('Deposit cannot be negative.')
        except Exception:
            errors.append('Invalid initial deposit amount.')
            initial_deposit = Decimal('0.00')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return redirect(url_for('admin.customers'))

        try:
            new_user = User(
                username=username,
                email=email,
                role='customer',
                is_active=True
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.flush()

            cust_code = Customer.generate_customer_code()
            new_customer = Customer(
                user_id=new_user.id,
                customer_code=cust_code,
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
            db.session.flush()

            acc_num = Account.generate_account_number()
            new_account = Account(
                customer_id=new_customer.id,
                account_number=acc_num,
                account_type=account_type,
                balance=initial_deposit,
                status='ACTIVE'
            )
            db.session.add(new_account)
            db.session.flush()

            if initial_deposit > 0:
                txn = Transaction(
                    transaction_ref=Transaction.generate_txn_ref(),
                    account_id=new_account.id,
                    transaction_type='DEPOSIT',
                    amount=initial_deposit,
                    balance_after=initial_deposit,
                    description='Admin Account Creation Opening Deposit',
                    status='COMPLETED'
                )
                db.session.add(txn)

            notify_user(
                new_user.id,
                'Account Created by Admin',
                f"Welcome to SmartBank! Your account {acc_num} has been provisioned with balance ₹{initial_deposit:,.2f}.",
                'SUCCESS'
            )

            db.session.commit()
            flash(f"Customer {first_name} {last_name} created successfully with ID {cust_code} and Account {acc_num}!", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f"Failed to create customer: {str(e)}", 'danger')

        return redirect(url_for('admin.customers'))

    # GET Request: Search and Filter Customers
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'ALL')
    page = request.args.get('page', 1, type=int)

    query = Customer.query.join(User)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Customer.customer_code.ilike(search_pattern)) |
            (Customer.first_name.ilike(search_pattern)) |
            (Customer.last_name.ilike(search_pattern)) |
            (Customer.phone.ilike(search_pattern)) |
            (User.email.ilike(search_pattern)) |
            (User.username.ilike(search_pattern))
        )

    if status_filter == 'ACTIVE':
        query = query.filter(User.is_active == True)
    elif status_filter == 'INACTIVE':
        query = query.filter(User.is_active == False)

    query = query.order_by(Customer.created_at.desc())
    per_page = current_app.config.get('ITEMS_PER_PAGE', 10)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'admin/customers.html',
        customers=pagination.items,
        pagination=pagination,
        search=search,
        status_filter=status_filter
    )


@admin_bp.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_customer(customer_id):
    """Admin Customer CRUD: Edit customer details and KYC status."""
    customer = Customer.query.get_or_404(customer_id)
    user = customer.user

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip().lower()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        pincode = request.form.get('pincode', '').strip()
        kyc_status = request.form.get('kyc_status', 'VERIFIED')

        if not first_name or not last_name or not phone or not email:
            flash('Name, phone, and email are required fields.', 'danger')
            return render_template('admin/customer_edit.html', customer=customer)

        if email != user.email:
            existing = User.query.filter_by(email=email).first()
            if existing and existing.id != user.id:
                flash(f"Email '{email}' is already taken.", 'danger')
                return render_template('admin/customer_edit.html', customer=customer)

        try:
            customer.first_name = first_name
            customer.last_name = last_name
            customer.phone = phone
            customer.address = address
            customer.city = city
            customer.state = state
            customer.pincode = pincode
            customer.kyc_status = kyc_status
            user.email = email

            db.session.commit()
            flash(f"Customer {customer.full_name} details updated successfully.", 'success')
            notify_user(user.id, 'Account Information Updated', 'An administrator updated your account profile information.', 'INFO')
            return redirect(url_for('admin.customers'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating customer: {str(e)}", 'danger')

    return render_template('admin/customer_edit.html', customer=customer)


@admin_bp.route('/customers/<int:customer_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_customer_status(customer_id):
    """Admin Soft Deletion / Re-activation of Customer and their accounts."""
    customer = Customer.query.get_or_404(customer_id)
    user = customer.user

    try:
        user.is_active = not user.is_active
        new_status = 'ACTIVE' if user.is_active else 'INACTIVE'

        # Also cascade status to accounts
        for acc in customer.accounts:
            acc.status = new_status

        action_word = 'activated' if user.is_active else 'deactivated'
        notify_user(
            user.id,
            f"Account {action_word.capitalize()}",
            f"Your SmartBank user account and associated bank accounts have been {action_word} by an administrator.",
            'SUCCESS' if user.is_active else 'DANGER'
        )

        db.session.commit()
        flash(f"Customer {customer.full_name} has been {action_word} successfully.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Status update failed: {str(e)}", 'danger')

    return redirect(url_for('admin.customers'))


@admin_bp.route('/accounts')
@login_required
@admin_required
def accounts():
    """Admin Accounts Management: View all accounts, filter by type/status, search."""
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'ALL')
    type_filter = request.args.get('type', 'ALL')
    page = request.args.get('page', 1, type=int)

    query = Account.query.join(Customer)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Account.account_number.ilike(search_pattern)) |
            (Customer.first_name.ilike(search_pattern)) |
            (Customer.last_name.ilike(search_pattern)) |
            (Customer.customer_code.ilike(search_pattern))
        )

    if status_filter != 'ALL':
        query = query.filter(Account.status == status_filter)

    if type_filter != 'ALL':
        query = query.filter(Account.account_type == type_filter)

    query = query.order_by(Account.created_at.desc())
    per_page = current_app.config.get('ITEMS_PER_PAGE', 10)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'admin/accounts.html',
        accounts=pagination.items,
        pagination=pagination,
        search=search,
        status_filter=status_filter,
        type_filter=type_filter
    )


@admin_bp.route('/accounts/<int:account_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_account_status(account_id):
    """Admin toggle specific account status between ACTIVE and INACTIVE/SUSPENDED."""
    account = Account.query.get_or_404(account_id)
    new_status = request.form.get('status', 'ACTIVE')

    if new_status not in ['ACTIVE', 'INACTIVE', 'SUSPENDED']:
        new_status = 'ACTIVE'

    try:
        old_status = account.status
        account.status = new_status
        db.session.commit()

        notify_user(
            account.customer.user_id,
            'Account Status Changed',
            f"Your account {account.account_number} status changed from {old_status} to {new_status}.",
            'INFO' if new_status == 'ACTIVE' else 'WARNING'
        )

        flash(f"Account {account.account_number} status updated to {new_status}.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating account status: {str(e)}", 'danger')

    return redirect(url_for('admin.accounts'))


@admin_bp.route('/transactions')
@login_required
@admin_required
def transactions():
    """Admin Global Transactions View with filters, search, and pagination."""
    search = request.args.get('q', '').strip()
    txn_type = request.args.get('type', 'ALL')
    page = request.args.get('page', 1, type=int)

    query = Transaction.query.join(Account).join(Customer)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Transaction.transaction_ref.ilike(search_pattern)) |
            (Account.account_number.ilike(search_pattern)) |
            (Transaction.recipient_account.ilike(search_pattern)) |
            (Customer.first_name.ilike(search_pattern)) |
            (Customer.last_name.ilike(search_pattern))
        )

    if txn_type != 'ALL':
        query = query.filter(Transaction.transaction_type == txn_type)

    query = query.order_by(Transaction.created_at.desc())
    per_page = current_app.config.get('ITEMS_PER_PAGE', 15)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'admin/transactions.html',
        transactions=pagination.items,
        pagination=pagination,
        search=search,
        txn_type=txn_type
    )
