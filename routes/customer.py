import re
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, User, Customer, Account, Transaction, Beneficiary, Notification
from routes.helpers import login_required, customer_required, get_current_user, get_current_customer, notify_user

customer_bp = Blueprint('customer', __name__, url_prefix='/customer')

@customer_bp.route('/dashboard')
@login_required
@customer_required
def dashboard():
    """Customer Dashboard with account overview, stats, and recent transactions."""
    customer = get_current_customer()
    if not customer:
        flash('Customer profile not found.', 'danger')
        return redirect(url_for('auth.login'))

    accounts = customer.accounts.all()
    primary_acc = customer.primary_account

    # Calculate statistics across all active accounts
    account_ids = [acc.id for acc in accounts]
    
    total_balance = customer.total_balance

    # Aggregated transaction statistics
    if account_ids:
        all_txns = Transaction.query.filter(Transaction.account_id.in_(account_ids))
        total_deposits = sum(
            float(t.amount) for t in all_txns.filter_by(transaction_type='DEPOSIT', status='COMPLETED').all()
        )
        total_withdrawals = sum(
            float(t.amount) for t in all_txns.filter_by(transaction_type='WITHDRAWAL', status='COMPLETED').all()
        )
        total_transfers = sum(
            float(t.amount) for t in all_txns.filter(
                Transaction.transaction_type.in_(['TRANSFER_SENT', 'TRANSFER_RECEIVED']),
                Transaction.status == 'COMPLETED'
            ).all()
        )
        recent_transactions = all_txns.order_by(Transaction.created_at.desc()).limit(7).all()
    else:
        total_deposits = 0.0
        total_withdrawals = 0.0
        total_transfers = 0.0
        recent_transactions = []

    # Unread notifications count
    unread_notifs = Notification.query.filter_by(user_id=customer.user_id, is_read=False).count()

    return render_template(
        'customer/dashboard.html',
        customer=customer,
        primary_acc=primary_acc,
        accounts=accounts,
        total_balance=total_balance,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        total_transfers=total_transfers,
        recent_transactions=recent_transactions,
        unread_notifs=unread_notifs
    )


@customer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@customer_required
def profile():
    """Customer profile view and update (Customer CRUD - Update)."""
    customer = get_current_customer()
    user = customer.user

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip().lower()
            address = request.form.get('address', '').strip()
            city = request.form.get('city', '').strip()
            state = request.form.get('state', '').strip()
            pincode = request.form.get('pincode', '').strip()

            errors = []
            if not first_name or not last_name:
                errors.append('First and last name cannot be empty.')
            if not phone or not re.match(r'^\+?[0-9]{10,15}$', phone.replace(' ', '')):
                errors.append('Please provide a valid phone number.')
            if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                errors.append('Please provide a valid email address.')

            # Check if email changed and is taken by another user
            if email != user.email:
                existing = User.query.filter_by(email=email).first()
                if existing and existing.id != user.id:
                    errors.append(f"Email '{email}' is already in use by another user.")

            if errors:
                for err in errors:
                    flash(err, 'danger')
                return render_template('customer/profile.html', customer=customer, user=user)

            try:
                customer.first_name = first_name
                customer.last_name = last_name
                customer.phone = phone
                customer.address = address
                customer.city = city
                customer.state = state
                customer.pincode = pincode
                user.email = email
                session['email'] = email
                session['customer_name'] = customer.full_name

                db.session.commit()
                flash('Profile details updated successfully.', 'success')
                notify_user(user.id, 'Profile Updated', 'Your profile contact details were updated successfully.', 'INFO')
                return redirect(url_for('customer.profile'))
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating profile: {str(e)}", 'danger')

        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')

            if not user.check_password(current_pwd):
                flash('Current password entered is incorrect.', 'danger')
                return render_template('customer/profile.html', customer=customer, user=user)

            if len(new_pwd) < 6:
                flash('New password must be at least 6 characters.', 'danger')
                return render_template('customer/profile.html', customer=customer, user=user)

            if new_pwd != confirm_pwd:
                flash('New password and confirmation do not match.', 'danger')
                return render_template('customer/profile.html', customer=customer, user=user)

            try:
                user.set_password(new_pwd)
                db.session.commit()
                flash('Password changed successfully!', 'success')
                notify_user(user.id, 'Security Alert', 'Your SmartBank account password was changed successfully.', 'WARNING')
                return redirect(url_for('customer.profile'))
            except Exception as e:
                db.session.rollback()
                flash(f"Error changing password: {str(e)}", 'danger')

    return render_template('customer/profile.html', customer=customer, user=user)


@customer_bp.route('/accounts')
@login_required
@customer_required
def accounts():
    """List all accounts for current customer."""
    customer = get_current_customer()
    user_accounts = customer.accounts.all()
    return render_template('customer/accounts.html', customer=customer, accounts=user_accounts)


@customer_bp.route('/accounts/create', methods=['POST'])
@login_required
@customer_required
def create_account():
    """Customer self-service to open an additional account (Savings, Current, Salary)."""
    customer = get_current_customer()
    account_type = request.form.get('account_type', 'Savings')
    initial_deposit_str = request.form.get('initial_deposit', '0').strip()

    if account_type not in ['Savings', 'Current', 'Salary']:
        account_type = 'Savings'

    try:
        initial_deposit = Decimal(initial_deposit_str) if initial_deposit_str else Decimal('0.00')
        if initial_deposit < 0:
            flash('Initial deposit amount cannot be negative.', 'danger')
            return redirect(url_for('customer.accounts'))
    except Exception:
        flash('Invalid deposit amount entered.', 'danger')
        return redirect(url_for('customer.accounts'))

    try:
        acc_num = Account.generate_account_number()
        new_acc = Account(
            customer_id=customer.id,
            account_number=acc_num,
            account_type=account_type,
            balance=initial_deposit,
            status='ACTIVE',
            currency='INR'
        )
        db.session.add(new_acc)
        db.session.flush()

        if initial_deposit > 0:
            txn = Transaction(
                transaction_ref=Transaction.generate_txn_ref(),
                account_id=new_acc.id,
                transaction_type='DEPOSIT',
                amount=initial_deposit,
                balance_after=initial_deposit,
                description=f'Opening balance for {account_type} Account',
                status='COMPLETED'
            )
            db.session.add(txn)

        notify_user(
            customer.user_id,
            'New Account Opened',
            f"Your new {account_type} Account ({acc_num}) is now active with balance ₹{initial_deposit:,.2f}.",
            'SUCCESS'
        )
        db.session.commit()
        flash(f"New {account_type} Account {acc_num} opened successfully!", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to create account: {str(e)}", 'danger')

    return redirect(url_for('customer.accounts'))


@customer_bp.route('/beneficiaries', methods=['GET', 'POST'])
@login_required
@customer_required
def beneficiaries():
    """Beneficiary management: View list and add new beneficiary."""
    customer = get_current_customer()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        account_number = request.form.get('account_number', '').strip()
        bank_name = request.form.get('bank_name', 'SmartBank').strip()
        ifsc_code = request.form.get('ifsc_code', 'SMRT0001001').strip().upper()
        email = request.form.get('email', '').strip()

        errors = []
        if not name:
            errors.append('Beneficiary name is required.')
        if not account_number or len(account_number) < 8:
            errors.append('Valid account number is required.')
        if not ifsc_code:
            errors.append('IFSC code is required.')

        # Check duplicate beneficiary for this customer
        existing = Beneficiary.query.filter_by(
            customer_id=customer.id,
            account_number=account_number
        ).first()
        if existing:
            errors.append('This account number is already saved in your beneficiaries.')

        # Check self-account
        cust_accounts = [acc.account_number for acc in customer.accounts]
        if account_number in cust_accounts:
            errors.append('You cannot add your own account as a beneficiary.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return redirect(url_for('customer.beneficiaries'))

        try:
            beneficiary = Beneficiary(
                customer_id=customer.id,
                name=name,
                account_number=account_number,
                bank_name=bank_name,
                ifsc_code=ifsc_code,
                email=email if email else None
            )
            db.session.add(beneficiary)
            db.session.commit()
            flash(f"Beneficiary '{name}' added successfully.", 'success')
            notify_user(
                customer.user_id,
                'Beneficiary Added',
                f"Beneficiary {name} ({account_number}) was successfully added to your payee list.",
                'INFO'
            )
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding beneficiary: {str(e)}", 'danger')

        return redirect(url_for('customer.beneficiaries'))

    saved_beneficiaries = customer.beneficiaries.order_by(Beneficiary.created_at.desc()).all()
    return render_template('customer/beneficiaries.html', customer=customer, beneficiaries=saved_beneficiaries)


@customer_bp.route('/beneficiaries/edit/<int:beneficiary_id>', methods=['POST'])
@login_required
@customer_required
def edit_beneficiary(beneficiary_id):
    """Edit an existing beneficiary."""
    customer = get_current_customer()
    beneficiary = Beneficiary.query.filter_by(id=beneficiary_id, customer_id=customer.id).first_or_404()

    name = request.form.get('name', '').strip()
    bank_name = request.form.get('bank_name', '').strip()
    ifsc_code = request.form.get('ifsc_code', '').strip().upper()
    email = request.form.get('email', '').strip()

    if not name or not bank_name or not ifsc_code:
        flash('All fields are required to update beneficiary.', 'danger')
        return redirect(url_for('customer.beneficiaries'))

    try:
        beneficiary.name = name
        beneficiary.bank_name = bank_name
        beneficiary.ifsc_code = ifsc_code
        beneficiary.email = email if email else None
        db.session.commit()
        flash('Beneficiary details updated successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating beneficiary: {str(e)}", 'danger')

    return redirect(url_for('customer.beneficiaries'))


@customer_bp.route('/beneficiaries/delete/<int:beneficiary_id>', methods=['POST'])
@login_required
@customer_required
def delete_beneficiary(beneficiary_id):
    """Delete a saved beneficiary."""
    customer = get_current_customer()
    beneficiary = Beneficiary.query.filter_by(id=beneficiary_id, customer_id=customer.id).first_or_404()

    try:
        name = beneficiary.name
        db.session.delete(beneficiary)
        db.session.commit()
        flash(f"Beneficiary '{name}' was removed successfully.", 'info')
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting beneficiary: {str(e)}", 'danger')

    return redirect(url_for('customer.beneficiaries'))


@customer_bp.route('/notifications')
@login_required
def notifications():
    """View customer notifications and manage read status."""
    user = get_current_user()
    user_notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).all()
    return render_template('customer/notifications.html', notifications=user_notifications)


@customer_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all unread notifications as read."""
    user = get_current_user()
    Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('customer.notifications'))
