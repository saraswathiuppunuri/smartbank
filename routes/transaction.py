from datetime import datetime
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import db, Account, Transaction, Beneficiary
from routes.helpers import login_required, customer_required, get_current_customer, notify_user

transaction_bp = Blueprint('transactions', __name__)

@transaction_bp.route('/deposit', methods=['GET', 'POST'])
@login_required
@customer_required
def deposit():
    """Deposit money into customer bank account with ACID guarantees."""
    customer = get_current_customer()
    accounts = customer.accounts.filter_by(status='ACTIVE').all()

    if not accounts:
        flash('You do not have any active accounts eligible for deposit.', 'warning')
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        account_id = request.form.get('account_id')
        amount_str = request.form.get('amount', '').strip()
        description = request.form.get('description', 'Cash/Online Deposit').strip()

        # Validate Account
        account = Account.query.filter_by(id=account_id, customer_id=customer.id, status='ACTIVE').first()
        if not account:
            flash('Invalid account selected or account is not active.', 'danger')
            return render_template('customer/deposit.html', accounts=accounts)

        # Validate Amount
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                flash('Deposit amount must be strictly greater than zero.', 'danger')
                return render_template('customer/deposit.html', accounts=accounts, selected_account=account)
            if amount > Decimal('1000000.00'):
                flash('Maximum deposit limit per transaction is ₹10,00,000.00.', 'danger')
                return render_template('customer/deposit.html', accounts=accounts, selected_account=account)
        except Exception:
            flash('Please enter a valid numeric deposit amount.', 'danger')
            return render_template('customer/deposit.html', accounts=accounts, selected_account=account)

        # Atomic Deposit Transaction
        try:
            account.balance = Decimal(str(account.balance)) + amount
            new_balance = account.balance
            txn_ref = Transaction.generate_txn_ref(prefix="DEP")

            txn = Transaction(
                transaction_ref=txn_ref,
                account_id=account.id,
                transaction_type='DEPOSIT',
                amount=amount,
                balance_after=new_balance,
                recipient_account=None,
                description=description or 'Deposit',
                status='COMPLETED'
            )
            db.session.add(txn)

            # Notification
            notify_user(
                customer.user_id,
                'Deposit Successful',
                f"₹{amount:,.2f} has been deposited into your account {account.account_number}. Updated balance: ₹{new_balance:,.2f}. Ref: {txn_ref}",
                'SUCCESS'
            )

            db.session.commit()
            flash(f"Successfully deposited ₹{amount:,.2f} into account {account.account_number}! Updated balance: ₹{new_balance:,.2f} (Ref: {txn_ref})", 'success')
            return redirect(url_for('transactions.history'))

        except Exception as e:
            db.session.rollback()
            flash(f"Deposit transaction failed: {str(e)}", 'danger')

    return render_template('customer/deposit.html', accounts=accounts)


@transaction_bp.route('/withdraw', methods=['GET', 'POST'])
@login_required
@customer_required
def withdraw():
    """Withdraw funds from account with balance and limit verification."""
    customer = get_current_customer()
    accounts = customer.accounts.filter_by(status='ACTIVE').all()

    if not accounts:
        flash('You do not have any active accounts eligible for withdrawals.', 'warning')
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        account_id = request.form.get('account_id')
        amount_str = request.form.get('amount', '').strip()
        description = request.form.get('description', 'ATM/Online Withdrawal').strip()

        # Validate Account
        account = Account.query.filter_by(id=account_id, customer_id=customer.id, status='ACTIVE').first()
        if not account:
            flash('Invalid account selected or account is not active.', 'danger')
            return render_template('customer/withdraw.html', accounts=accounts)

        # Validate Amount
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                flash('Withdrawal amount must be strictly greater than zero.', 'danger')
                return render_template('customer/withdraw.html', accounts=accounts, selected_account=account)
        except Exception:
            flash('Please enter a valid numeric withdrawal amount.', 'danger')
            return render_template('customer/withdraw.html', accounts=accounts, selected_account=account)

        # Balance Verification
        current_balance = Decimal(str(account.balance))
        if amount > current_balance:
            flash(f"Insufficient funds! Available balance is ₹{current_balance:,.2f}, which is less than requested ₹{amount:,.2f}.", 'danger')
            # Log failed transaction notification
            notify_user(
                customer.user_id,
                'Withdrawal Declined',
                f"Attempted withdrawal of ₹{amount:,.2f} from {account.account_number} was declined due to insufficient funds.",
                'DANGER'
            )
            return render_template('customer/withdraw.html', accounts=accounts, selected_account=account)

        # Atomic Withdrawal Transaction
        try:
            account.balance = current_balance - amount
            new_balance = account.balance
            txn_ref = Transaction.generate_txn_ref(prefix="WTH")

            txn = Transaction(
                transaction_ref=txn_ref,
                account_id=account.id,
                transaction_type='WITHDRAWAL',
                amount=amount,
                balance_after=new_balance,
                recipient_account=None,
                description=description or 'Withdrawal',
                status='COMPLETED'
            )
            db.session.add(txn)

            # Notification
            notify_user(
                customer.user_id,
                'Withdrawal Successful',
                f"₹{amount:,.2f} was withdrawn from account {account.account_number}. Remaining balance: ₹{new_balance:,.2f}. Ref: {txn_ref}",
                'INFO'
            )

            # Low balance alert if threshold breached
            low_limit = Decimal(str(current_app.config.get('LOW_BALANCE_THRESHOLD', 1000.00)))
            if new_balance < low_limit:
                notify_user(
                    customer.user_id,
                    'Low Balance Alert',
                    f"Warning: Account {account.account_number} balance (₹{new_balance:,.2f}) has dropped below the threshold of ₹{low_limit:,.2f}.",
                    'WARNING'
                )

            db.session.commit()
            flash(f"Successfully withdrawn ₹{amount:,.2f} from account {account.account_number}! Remaining balance: ₹{new_balance:,.2f}", 'success')
            return redirect(url_for('transactions.history'))

        except Exception as e:
            db.session.rollback()
            flash(f"Withdrawal failed: {str(e)}", 'danger')

    return render_template('customer/withdraw.html', accounts=accounts)


@transaction_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
@customer_required
def transfer():
    """Secure fund transfer between bank accounts with atomic debit/credit rollback."""
    customer = get_current_customer()
    accounts = customer.accounts.filter_by(status='ACTIVE').all()
    saved_beneficiaries = customer.beneficiaries.all()

    if not accounts:
        flash('You have no active accounts to transfer funds from.', 'warning')
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        source_account_id = request.form.get('source_account_id')
        recipient_account_num = request.form.get('recipient_account_number', '').strip()
        amount_str = request.form.get('amount', '').strip()
        description = request.form.get('description', 'Fund Transfer').strip()

        # Validate Source Account
        source_account = Account.query.filter_by(id=source_account_id, customer_id=customer.id, status='ACTIVE').first()
        if not source_account:
            flash('Invalid source account selected.', 'danger')
            return render_template('customer/transfer.html', accounts=accounts, beneficiaries=saved_beneficiaries)

        # Validate Recipient Account
        if not recipient_account_num:
            flash('Recipient account number is required.', 'danger')
            return render_template('customer/transfer.html', accounts=accounts, beneficiaries=saved_beneficiaries)

        if source_account.account_number == recipient_account_num:
            flash('Source and recipient accounts cannot be identical.', 'danger')
            return render_template('customer/transfer.html', accounts=accounts, beneficiaries=saved_beneficiaries)

        recipient_account = Account.query.filter_by(account_number=recipient_account_num).first()
        if not recipient_account:
            flash(f"Recipient account '{recipient_account_num}' does not exist in SmartBank system.", 'danger')
            return render_template('customer/transfer.html', accounts=accounts, beneficiaries=saved_beneficiaries)

        if recipient_account.status != 'ACTIVE':
            flash('Recipient account is currently inactive or suspended and cannot accept transfers.', 'danger')
            return render_template('customer/transfer.html', accounts=accounts, beneficiaries=saved_beneficiaries)

        # Validate Amount
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                flash('Transfer amount must be strictly greater than zero.', 'danger')
                return render_template('customer/transfer.html', accounts=accounts, beneficiaries=saved_beneficiaries)
        except Exception:
            flash('Please enter a valid numeric transfer amount.', 'danger')
            return render_template('customer/transfer.html', accounts=accounts, beneficiaries=saved_beneficiaries)

        # Validate sender balance
        sender_balance = Decimal(str(source_account.balance))
        if amount > sender_balance:
            flash(f"Insufficient funds! Your balance is ₹{sender_balance:,.2f}, requested transfer is ₹{amount:,.2f}.", 'danger')
            notify_user(
                customer.user_id,
                'Transfer Failed',
                f"Transfer of ₹{amount:,.2f} to {recipient_account_num} failed due to insufficient balance.",
                'DANGER'
            )
            return render_template('customer/transfer.html', accounts=accounts, beneficiaries=saved_beneficiaries)

        # ATOMIC TRANSFER TRANSACTION
        try:
            # 1. Deduct from Sender
            source_account.balance = sender_balance - amount
            sender_new_balance = source_account.balance

            # 2. Add to Recipient
            recipient_current_balance = Decimal(str(recipient_account.balance))
            recipient_account.balance = recipient_current_balance + amount
            recipient_new_balance = recipient_account.balance

            # 3. Create Transaction Reference
            txn_ref = Transaction.generate_txn_ref(prefix="TRF")

            # 4. Sender Ledger Entry
            sender_txn = Transaction(
                transaction_ref=txn_ref,
                account_id=source_account.id,
                transaction_type='TRANSFER_SENT',
                amount=amount,
                balance_after=sender_new_balance,
                recipient_account=recipient_account.account_number,
                description=f"Transfer to {recipient_account.customer.full_name} ({recipient_account.account_number}): {description}",
                status='COMPLETED'
            )
            db.session.add(sender_txn)

            # 5. Recipient Ledger Entry
            recipient_ref = f"{txn_ref}-R"
            recipient_txn = Transaction(
                transaction_ref=recipient_ref,
                account_id=recipient_account.id,
                transaction_type='TRANSFER_RECEIVED',
                amount=amount,
                balance_after=recipient_new_balance,
                recipient_account=source_account.account_number,
                description=f"Transfer from {customer.full_name} ({source_account.account_number}): {description}",
                status='COMPLETED'
            )
            db.session.add(recipient_txn)

            # 6. Notifications for Sender and Recipient
            notify_user(
                customer.user_id,
                'Transfer Sent',
                f"₹{amount:,.2f} transferred successfully to {recipient_account.customer.full_name} ({recipient_account.account_number}). Remaining balance: ₹{sender_new_balance:,.2f}. Ref: {txn_ref}",
                'SUCCESS'
            )
            notify_user(
                recipient_account.customer.user_id,
                'Transfer Received',
                f"You received ₹{amount:,.2f} from {customer.full_name} into account {recipient_account.account_number}. Updated balance: ₹{recipient_new_balance:,.2f}.",
                'SUCCESS'
            )

            # 7. Check low balance alert for sender
            low_limit = Decimal(str(current_app.config.get('LOW_BALANCE_THRESHOLD', 1000.00)))
            if sender_new_balance < low_limit:
                notify_user(
                    customer.user_id,
                    'Low Balance Alert',
                    f"Warning: Your account {source_account.account_number} balance (₹{sender_new_balance:,.2f}) is below ₹{low_limit:,.2f}.",
                    'WARNING'
                )

            # Commit atomicity
            db.session.commit()
            flash(f"Transfer of ₹{amount:,.2f} to {recipient_account.customer.full_name} ({recipient_account.account_number}) completed successfully! Ref: {txn_ref}", 'success')
            return redirect(url_for('transactions.history'))

        except Exception as e:
            db.session.rollback()
            flash(f"Fund transfer failed due to transaction error: {str(e)}", 'danger')

    # If beneficiary was preselected via query parameter
    prefill_beneficiary = request.args.get('beneficiary_acc', '')

    return render_template(
        'customer/transfer.html',
        accounts=accounts,
        beneficiaries=saved_beneficiaries,
        prefill_beneficiary=prefill_beneficiary
    )


@transaction_bp.route('/history')
@login_required
@customer_required
def history():
    """Transaction history with search, filters, pagination, and sorting."""
    customer = get_current_customer()
    user_account_ids = [acc.id for acc in customer.accounts.all()]

    if not user_account_ids:
        return render_template('customer/transactions.html', transactions=[], pagination=None)

    # Query params
    page = request.args.get('page', 1, type=int)
    txn_type = request.args.get('type', 'ALL').strip().upper()
    search = request.args.get('q', '').strip()
    account_filter = request.args.get('account', '').strip()
    date_from = request.args.get('from_date', '').strip()
    date_to = request.args.get('to_date', '').strip()
    sort_by = request.args.get('sort', 'newest').strip()

    query = Transaction.query.filter(Transaction.account_id.in_(user_account_ids))

    # Filter by transaction type
    if txn_type and txn_type != 'ALL':
        query = query.filter(Transaction.transaction_type == txn_type)

    # Filter by specific account
    if account_filter:
        account_obj = Account.query.filter_by(account_number=account_filter, customer_id=customer.id).first()
        if account_obj:
            query = query.filter(Transaction.account_id == account_obj.id)

    # Search by ref or description or recipient
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Transaction.transaction_ref.ilike(search_pattern)) |
            (Transaction.description.ilike(search_pattern)) |
            (Transaction.recipient_account.ilike(search_pattern))
        )

    # Date filters
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Transaction.created_at >= dt_from)
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S')
            query = query.filter(Transaction.created_at <= dt_to)
        except ValueError:
            pass

    # Sorting
    if sort_by == 'oldest':
        query = query.order_by(Transaction.created_at.asc())
    elif sort_by == 'amount_desc':
        query = query.order_by(Transaction.amount.desc())
    elif sort_by == 'amount_asc':
        query = query.order_by(Transaction.amount.asc())
    else:  # newest
        query = query.order_by(Transaction.created_at.desc())

    # Pagination
    per_page = current_app.config.get('ITEMS_PER_PAGE', 10)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        'customer/transactions.html',
        transactions=pagination.items,
        pagination=pagination,
        txn_type=txn_type,
        search=search,
        account_filter=account_filter,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        user_accounts=customer.accounts.all()
    )
