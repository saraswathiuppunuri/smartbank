import base64
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from models import db, User, Customer, Account, Transaction, Notification, BranchCashRequest
from routes.helpers import login_required, customer_required, admin_required, get_current_user, get_current_customer, notify_user

branch_cash_bp = Blueprint('branch_cash', __name__, url_prefix='/branch-cash')


# ====================================================================
# CUSTOMER ROUTES: Online Withdrawal Slip & Token Management
# ====================================================================

@branch_cash_bp.route('/')
@login_required
@customer_required
def index():
    """Customer dashboard for branch cash requests / digital withdrawal slips."""
    customer = get_current_customer()
    requests = BranchCashRequest.query.filter_by(customer_id=customer.id).order_by(BranchCashRequest.created_at.desc()).all()
    
    # Calculate stats
    total_requested = sum(float(r.amount) for r in requests if r.status in ('PENDING', 'APPROVED'))
    active_requests_count = len([r for r in requests if r.status in ('PENDING', 'APPROVED')])
    
    return render_template(
        'customer/branch_cash_list.html',
        customer=customer,
        requests=requests,
        total_requested=total_requested,
        active_requests_count=active_requests_count,
        branches=BranchCashRequest.BRANCHES
    )


@branch_cash_bp.route('/new', methods=['GET', 'POST'])
@login_required
@customer_required
def new_slip():
    """Form to submit an Online Cash Withdrawal Slip / Pre-Booking."""
    customer = get_current_customer()
    accounts = customer.accounts.filter_by(status='ACTIVE').all()

    if not accounts:
        flash('You need an active bank account to request a cash withdrawal.', 'warning')
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        account_id = request.form.get('account_id')
        account_number_str = request.form.get('account_number', '').strip()
        account_holder_name = request.form.get('account_holder_name', '').strip()
        branch_code = request.form.get('branch_code', '').strip().upper()
        amount_str = request.form.get('amount', '').strip()
        visit_date_str = request.form.get('visit_date', '').strip()
        time_slot = request.form.get('time_slot', '').strip()
        purpose = request.form.get('purpose', '').strip()
        denomination = request.form.get('denomination_preference', '').strip()
        signature_data = request.form.get('signature_data', '').strip()

        # 1. Validate Account (by number or id)
        account = None
        if account_number_str:
            account = Account.query.filter_by(account_number=account_number_str, customer_id=customer.id, status='ACTIVE').first()
            if not account:
                other_acc = Account.query.filter_by(account_number=account_number_str).first()
                if other_acc:
                    flash(f"Account number {account_number_str} belongs to a different customer profile. You can only withdraw from your own active account.", 'danger')
                    return redirect(url_for('branch_cash.new_slip'))
                else:
                    flash(f"Account number '{account_number_str}' was not found. Please verify your 12-digit account number.", 'danger')
                    return redirect(url_for('branch_cash.new_slip'))
        elif account_id:
            account = Account.query.filter_by(id=account_id, customer_id=customer.id, status='ACTIVE').first()

        if not account:
            flash('Please enter or select a valid active account number.', 'danger')
            return redirect(url_for('branch_cash.new_slip'))

        # 2. Validate Branch
        if branch_code not in BranchCashRequest.BRANCHES:
            flash('Please select a valid SmartBank branch.', 'danger')
            return redirect(url_for('branch_cash.new_slip'))
        
        branch_info = BranchCashRequest.BRANCHES[branch_code]

        # 3. Validate Amount
        try:
            amount = Decimal(amount_str)
            if amount < Decimal('1000.00'):
                flash('Minimum branch cash withdrawal pre-booking is ₹1,000.00.', 'danger')
                return redirect(url_for('branch_cash.new_slip'))
            if amount > Decimal('500000.00'):
                flash('Maximum single-day branch withdrawal pre-booking is ₹5,00,000.00. For higher corporate amounts, contact your branch manager.', 'danger')
                return redirect(url_for('branch_cash.new_slip'))
            if amount > account.balance:
                flash(f"Insufficient funds in account {account.account_number}. Available balance: ₹{account.balance:,.2f}.", 'danger')
                return redirect(url_for('branch_cash.new_slip'))
        except Exception:
            flash('Invalid cash amount entered.', 'danger')
            return redirect(url_for('branch_cash.new_slip'))

        # 4. Validate Visit Date
        try:
            visit_date = datetime.strptime(visit_date_str, '%Y-%m-%d').date()
            today = date.today()
            if visit_date < today:
                flash('Scheduled visit date cannot be in the past.', 'danger')
                return redirect(url_for('branch_cash.new_slip'))
            if visit_date > today + timedelta(days=14):
                flash('Branch cash requests can be scheduled up to 14 days in advance only.', 'danger')
                return redirect(url_for('branch_cash.new_slip'))
        except ValueError:
            flash('Please provide a valid visit date (YYYY-MM-DD).', 'danger')
            return redirect(url_for('branch_cash.new_slip'))

        # 5. Validate Time Slot & Purpose
        if not time_slot:
            time_slot = 'Morning: 10:00 AM - 12:00 PM'
        if not purpose:
            purpose = 'Personal Savings Withdrawal'

        # 6. Validate Signature
        if not signature_data:
            signature_data = f"DIGITALLY ACKNOWLEDGED BY {(account_holder_name or customer.full_name).upper()} ON {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"

        try:
            token = BranchCashRequest.generate_token(branch_code)
            amount_words = BranchCashRequest.amount_to_words(amount)

            cash_req = BranchCashRequest(
                token_number=token,
                customer_id=customer.id,
                account_holder_name=account_holder_name or customer.full_name,
                account_id=account.id,
                branch_code=branch_code,
                branch_name=branch_info['name'],
                ifsc_code=branch_info['ifsc'],
                amount=amount,
                amount_words=amount_words,
                visit_date=visit_date,
                time_slot=time_slot,
                purpose=purpose,
                denomination_preference=denomination or 'Standard Mix (₹500 & ₹200)',
                signature_data=signature_data,
                status='PENDING'
            )
            db.session.add(cash_req)

            # Customer Notification
            notify_user(
                customer.user_id,
                'Branch Cash Slip Submitted',
                f"Your online cash withdrawal slip for ₹{amount:,.2f} at {branch_info['name']} has been submitted. Token: {token}. Awaiting branch manager approval.",
                'INFO'
            )

            # System admin/manager notification
            admin_users = User.query.filter_by(role='admin').all()
            for admin in admin_users:
                notify_user(
                    admin.id,
                    'New Branch Cash Pre-Booking',
                    f"New withdrawal slip {token} submitted by {customer.full_name} for ₹{amount:,.2f} at {branch_info['name']}. Requires manager review.",
                    'WARNING'
                )

            db.session.commit()
            flash(f"Digital Withdrawal Slip submitted successfully! Your Fast-Track Token is: {token}. Cash is awaiting branch manager approval.", 'success')
            return redirect(url_for('branch_cash.view_slip', request_id=cash_req.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Failed to submit withdrawal slip: {str(e)}", 'danger')
            return redirect(url_for('branch_cash.new_slip'))

    # GET method
    min_date = date.today().strftime('%Y-%m-%d')
    max_date = (date.today() + timedelta(days=14)).strftime('%Y-%m-%d')

    return render_template(
        'customer/branch_cash_form.html',
        customer=customer,
        accounts=accounts,
        branches=BranchCashRequest.BRANCHES,
        time_slots=BranchCashRequest.TIME_SLOTS,
        purposes=BranchCashRequest.PURPOSES,
        min_date=min_date,
        max_date=max_date
    )


@branch_cash_bp.route('/slip/<int:request_id>')
@login_required
def view_slip(request_id):
    """View authentic digital cash withdrawal slip & fast-track token pass."""
    user = get_current_user()
    cash_req = db.session.get(BranchCashRequest, request_id)

    if not cash_req:
        flash('Withdrawal slip not found.', 'danger')
        return redirect(url_for('customer.dashboard'))

    # Security check: must be owner or admin
    if not user.is_admin and cash_req.customer.user_id != user.id:
        flash('Unauthorized access to withdrawal slip.', 'danger')
        return redirect(url_for('customer.dashboard'))

    branch_info = BranchCashRequest.BRANCHES.get(cash_req.branch_code, {
        'name': cash_req.branch_name,
        'ifsc': cash_req.ifsc_code,
        'address': 'SmartBank Branch',
        'phone': '1800-419-0123',
        'manager_name': 'Branch Operations Manager'
    })

    return render_template(
        'customer/branch_cash_slip.html',
        req=cash_req,
        branch=branch_info,
        is_admin=user.is_admin
    )


@branch_cash_bp.route('/<int:request_id>/cancel', methods=['POST'])
@login_required
@customer_required
def cancel_slip(request_id):
    """Cancel a pending cash withdrawal request."""
    customer = get_current_customer()
    cash_req = db.session.get(BranchCashRequest, request_id)

    if not cash_req or cash_req.customer_id != customer.id:
        flash('Request not found.', 'danger')
        return redirect(url_for('branch_cash.index'))

    if cash_req.status != 'PENDING':
        flash('Only pending cash requests can be cancelled.', 'warning')
        return redirect(url_for('branch_cash.view_slip', request_id=request_id))

    try:
        cash_req.status = 'EXPIRED'
        cash_req.manager_remarks = 'Cancelled by customer before branch processing.'
        db.session.commit()

        notify_user(
            customer.user_id,
            'Cash Request Cancelled',
            f"Your cash request {cash_req.token_number} for ₹{cash_req.amount:,.2f} has been cancelled.",
            'INFO'
        )
        flash('Cash withdrawal pre-booking has been cancelled.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f"Error cancelling request: {str(e)}", 'danger')

    return redirect(url_for('branch_cash.index'))


# ====================================================================
# MANAGER & ADMIN ROUTES: Virtual Form Verification & Fast-Track Dispense
# ====================================================================

@branch_cash_bp.route('/admin/requests')
@login_required
@admin_required
def admin_requests():
    """Branch Manager control center for reviewing online withdrawal slips."""
    branch_filter = request.args.get('branch', 'ALL').strip().upper()
    status_filter = request.args.get('status', 'ALL').strip().upper()

    query = BranchCashRequest.query

    if branch_filter != 'ALL' and branch_filter in BranchCashRequest.BRANCHES:
        query = query.filter_by(branch_code=branch_filter)
    if status_filter != 'ALL' and status_filter in ('PENDING', 'APPROVED', 'REJECTED', 'COLLECTED', 'EXPIRED'):
        query = query.filter_by(status=status_filter)

    requests = query.order_by(BranchCashRequest.created_at.desc()).all()

    # Aggregate Metrics
    all_requests = BranchCashRequest.query.all()
    total_requested_amount = sum(float(r.amount) for r in all_requests if r.status in ('PENDING', 'APPROVED', 'COLLECTED'))
    pending_count = len([r for r in all_requests if r.status == 'PENDING'])
    approved_count = len([r for r in all_requests if r.status == 'APPROVED'])
    collected_count = len([r for r in all_requests if r.status == 'COLLECTED'])

    return render_template(
        'admin/branch_cash_requests.html',
        requests=requests,
        branches=BranchCashRequest.BRANCHES,
        current_branch=branch_filter,
        current_status=status_filter,
        total_requested_amount=total_requested_amount,
        pending_count=pending_count,
        approved_count=approved_count,
        collected_count=collected_count
    )


@branch_cash_bp.route('/admin/<int:request_id>/approve', methods=['POST'])
@login_required
@admin_required
def admin_approve(request_id):
    """Manager approves virtual withdrawal slip and pre-assigns cash counter."""
    user = get_current_user()
    cash_req = db.session.get(BranchCashRequest, request_id)

    if not cash_req:
        flash('Withdrawal request not found.', 'danger')
        return redirect(url_for('branch_cash.admin_requests'))

    if cash_req.status != 'PENDING':
        flash(f"Cannot approve request with status '{cash_req.status}'.", 'warning')
        return redirect(url_for('branch_cash.admin_requests'))

    counter = request.form.get('priority_counter', 'Counter 2 (Fast-Track Cash)').strip()
    remarks = request.form.get('manager_remarks', 'Verified customer signature and balance. Cash reserved at counter.').strip()

    # Verify customer account still has sufficient funds
    if cash_req.amount > cash_req.account.balance:
        flash(f"Approval declined: Account {cash_req.account.account_number} balance (₹{cash_req.account.balance:,.2f}) is lower than requested amount (₹{cash_req.amount:,.2f}).", 'danger')
        return redirect(url_for('branch_cash.admin_requests'))

    try:
        cash_req.status = 'APPROVED'
        cash_req.manager_id = user.id
        cash_req.manager_remarks = remarks
        cash_req.priority_counter = counter
        cash_req.approved_at = datetime.now(timezone.utc)
        db.session.commit()

        # Notify Customer of Manager Approval
        notify_user(
            cash_req.customer.user_id,
            'Branch Cash Slip APPROVED by Manager! 🎉',
            f"Great news! Your withdrawal slip {cash_req.token_number} for ₹{cash_req.amount:,.2f} at {cash_req.branch_name} has been APPROVED by the Branch Manager. Cash is reserved at {counter}. Please arrive on {cash_req.visit_date.strftime('%d-%b-%Y')} ({cash_req.time_slot}) for zero-wait cash delivery.",
            'SUCCESS'
        )

        flash(f"Withdrawal Slip {cash_req.token_number} APPROVED! Cash reserved at {counter}. Customer notified.", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Error approving slip: {str(e)}", 'danger')

    return redirect(url_for('branch_cash.admin_requests'))


@branch_cash_bp.route('/admin/<int:request_id>/reject', methods=['POST'])
@login_required
@admin_required
def admin_reject(request_id):
    """Manager declines withdrawal slip with remarks."""
    user = get_current_user()
    cash_req = db.session.get(BranchCashRequest, request_id)

    if not cash_req:
        flash('Withdrawal request not found.', 'danger')
        return redirect(url_for('branch_cash.admin_requests'))

    remarks = request.form.get('manager_remarks', 'Declined per branch compliance guidelines.').strip()

    try:
        cash_req.status = 'REJECTED'
        cash_req.manager_id = user.id
        cash_req.manager_remarks = remarks
        db.session.commit()

        notify_user(
            cash_req.customer.user_id,
            'Branch Cash Slip Rejected',
            f"Your cash withdrawal slip {cash_req.token_number} for ₹{cash_req.amount:,.2f} at {cash_req.branch_name} was declined. Manager reason: {remarks}",
            'DANGER'
        )

        flash(f"Withdrawal Slip {cash_req.token_number} REJECTED. Customer notified.", 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f"Error declining slip: {str(e)}", 'danger')

    return redirect(url_for('branch_cash.admin_requests'))


@branch_cash_bp.route('/admin/<int:request_id>/dispense', methods=['POST'])
@login_required
@admin_required
def admin_dispense(request_id):
    """
    Branch Counter Offline Settlement:
    When the customer arrives at the physical branch, the teller verifies the pre-approved token,
    dispenses the physical currency, atomically debits the account, and writes the ledger record.
    """
    user = get_current_user()
    cash_req = db.session.get(BranchCashRequest, request_id)

    if not cash_req:
        flash('Request not found.', 'danger')
        return redirect(url_for('branch_cash.admin_requests'))

    if cash_req.status not in ('PENDING', 'APPROVED'):
        flash(f"Cannot dispense cash for request with status '{cash_req.status}'.", 'warning')
        return redirect(url_for('branch_cash.admin_requests'))

    account = cash_req.account
    if account.status != 'ACTIVE':
        flash('Cannot dispense cash: Linked customer account is not active.', 'danger')
        return redirect(url_for('branch_cash.admin_requests'))

    curr_balance = Decimal(str(account.balance))
    amount = Decimal(str(cash_req.amount))

    if amount > curr_balance:
        flash(f"Dispense Failed: Insufficient funds. Current balance: ₹{curr_balance:,.2f}, Requested: ₹{amount:,.2f}.", 'danger')
        return redirect(url_for('branch_cash.admin_requests'))

    # ATOMIC CASH DISBURSEMENT
    try:
        # 1. Deduct balance
        account.balance = curr_balance - amount
        new_balance = account.balance

        # 2. Record ledger transaction
        txn_ref = Transaction.generate_txn_ref(prefix="CSH")
        txn = Transaction(
            transaction_ref=txn_ref,
            account_id=account.id,
            transaction_type='BRANCH_WITHDRAWAL',
            amount=amount,
            balance_after=new_balance,
            recipient_account=f"{cash_req.branch_code} Cash Counter",
            description=f"Branch Offline Cash Withdrawal at {cash_req.branch_name} (Slip Ref: {cash_req.token_number})",
            status='COMPLETED'
        )
        db.session.add(txn)
        db.session.flush()

        # 3. Update Slip Status
        cash_req.status = 'COLLECTED'
        cash_req.collected_at = datetime.now(timezone.utc)
        cash_req.transaction_id = txn.id
        if not cash_req.manager_id:
            cash_req.manager_id = user.id

        # 4. Notify Customer
        notify_user(
            cash_req.customer.user_id,
            'Cash Collected at Branch Counter 💵',
            f"₹{amount:,.2f} cash was successfully dispensed to you at {cash_req.branch_name} ({cash_req.priority_counter or 'Counter 2'}). Slip: {cash_req.token_number}. Txn Ref: {txn_ref}. Remaining balance: ₹{new_balance:,.2f}.",
            'SUCCESS'
        )

        db.session.commit()
        flash(f"Cash of ₹{amount:,.2f} DISPENSED SUCCESSFULLY to {cash_req.customer.full_name}! Account debited. (Txn Ref: {txn_ref})", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Cash disbursement failed: {str(e)}", 'danger')

    return redirect(url_for('branch_cash.admin_requests'))
