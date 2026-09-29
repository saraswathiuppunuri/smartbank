import re
from datetime import datetime, timezone
from decimal import Decimal
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from models import db, Card, Account, Transaction, Notification
from routes.helpers import login_required, customer_required, get_current_customer, notify_user

card_bp = Blueprint('cards', __name__, url_prefix='/cards')

@card_bp.route('/')
@login_required
@customer_required
def index():
    """Debit cards overview, management controls, and usage simulator."""
    customer = get_current_customer()
    customer_account_ids = [acc.id for acc in customer.accounts.all()]

    if not customer_account_ids:
        flash('You need an active bank account before managing debit cards.', 'warning')
        return redirect(url_for('customer.accounts'))

    cards = Card.query.filter(Card.account_id.in_(customer_account_ids)).order_by(Card.created_at.desc()).all()
    active_accounts = customer.accounts.filter_by(status='ACTIVE').all()

    # Pre-calculate card usage history
    card_ids = [c.id for c in cards]
    card_transactions = []
    if card_ids:
        card_transactions = Transaction.query.filter(
            Transaction.card_id.in_(card_ids)
        ).order_by(Transaction.created_at.desc()).limit(10).all()

    return render_template(
        'customer/cards.html',
        customer=customer,
        cards=cards,
        accounts=active_accounts,
        card_transactions=card_transactions,
        current_year=datetime.now(timezone.utc).year
    )


@card_bp.route('/apply', methods=['POST'])
@login_required
@customer_required
def apply_card():
    """Apply for / issue a new debit card linked to an active account."""
    customer = get_current_customer()
    account_id = request.form.get('account_id')
    card_network = request.form.get('card_network', 'VISA').strip().upper()
    card_type = request.form.get('card_type', 'Platinum').strip()
    pin = request.form.get('pin', '').strip()
    confirm_pin = request.form.get('confirm_pin', '').strip()

    # Validations
    account = Account.query.filter_by(id=account_id, customer_id=customer.id, status='ACTIVE').first()
    if not account:
        flash('Invalid account selected or account is not active.', 'danger')
        return redirect(url_for('cards.index'))

    if card_network not in ['VISA', 'MASTERCARD', 'RUPAY']:
        card_network = 'VISA'
    if card_type not in ['Platinum', 'Classic', 'Business']:
        card_type = 'Platinum'

    if not pin or len(pin) != 4 or not pin.isdigit():
        flash('ATM PIN must be exactly 4 numeric digits.', 'danger')
        return redirect(url_for('cards.index'))

    if pin != confirm_pin:
        flash('PIN confirmation does not match.', 'danger')
        return redirect(url_for('cards.index'))

    try:
        card_number = Card.generate_card_number(network=card_network)
        cvv = Card.generate_cvv()
        now = datetime.now(timezone.utc)
        expiry_month = now.month
        expiry_year = now.year + 5  # Valid for 5 years

        new_card = Card(
            account_id=account.id,
            card_number=card_number,
            card_holder_name=customer.full_name.upper(),
            card_network=card_network,
            card_type=card_type,
            expiry_month=expiry_month,
            expiry_year=expiry_year,
            cvv=cvv,
            daily_limit=Decimal('50000.00'),
            status='ACTIVE',
            is_online_enabled=True,
            is_contactless_enabled=True,
            is_international_enabled=False
        )
        new_card.set_pin(pin)
        db.session.add(new_card)

        notify_user(
            customer.user_id,
            'Debit Card Issued',
            f"Your new {card_network} {card_type} Debit Card ending in {card_number[-4:]} for account {account.account_number} is now active.",
            'SUCCESS'
        )

        db.session.commit()
        flash(f"New {card_network} {card_type} Debit Card issued successfully! Card ends in {card_number[-4:]}.", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Failed to issue debit card: {str(e)}", 'danger')

    return redirect(url_for('cards.index'))


@card_bp.route('/<int:card_id>/toggle-lock', methods=['POST'])
@login_required
@customer_required
def toggle_lock(card_id):
    """Temporarily lock or unlock debit card."""
    customer = get_current_customer()
    card = db.session.get(Card, card_id)

    if not card or card.account.customer_id != customer.id:
        flash('Card not found or access denied.', 'danger')
        return redirect(url_for('cards.index'))

    if card.is_blocked:
        flash('This card is permanently blocked and cannot be unlocked.', 'danger')
        return redirect(url_for('cards.index'))

    try:
        if card.is_active:
            card.status = 'LOCKED'
            msg = f"Card ending in {card.card_number[-4:]} has been temporarily LOCKED for security."
            category = 'warning'
        else:
            card.status = 'ACTIVE'
            msg = f"Card ending in {card.card_number[-4:]} has been UNLOCKED and is ready for use."
            category = 'success'

        notify_user(customer.user_id, 'Card Security Status Update', msg, 'INFO')
        db.session.commit()
        flash(msg, category)

    except Exception as e:
        db.session.rollback()
        flash(f"Failed to change card status: {str(e)}", 'danger')

    return redirect(url_for('cards.index'))


@card_bp.route('/<int:card_id>/toggle-channel', methods=['POST'])
@login_required
@customer_required
def toggle_channel(card_id):
    """Toggle online, contactless, or international transaction permissions."""
    customer = get_current_customer()
    card = db.session.get(Card, card_id)

    if not card or card.account.customer_id != customer.id:
        flash('Card not found.', 'danger')
        return redirect(url_for('cards.index'))

    channel = request.form.get('channel')
    try:
        if channel == 'online':
            card.is_online_enabled = not card.is_online_enabled
            state = 'enabled' if card.is_online_enabled else 'disabled'
            flash(f"Online / E-Commerce transactions {state} for card {card.masked_card_number}.", 'info')
        elif channel == 'contactless':
            card.is_contactless_enabled = not card.is_contactless_enabled
            state = 'enabled' if card.is_contactless_enabled else 'disabled'
            flash(f"Contactless Tap & Pay {state} for card {card.masked_card_number}.", 'info')
        elif channel == 'international':
            card.is_international_enabled = not card.is_international_enabled
            state = 'enabled' if card.is_international_enabled else 'disabled'
            flash(f"International usage {state} for card {card.masked_card_number}.", 'info')

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to update channel preference: {str(e)}", 'danger')

    return redirect(url_for('cards.index'))


@card_bp.route('/<int:card_id>/update-limit', methods=['POST'])
@login_required
@customer_required
def update_limit(card_id):
    """Update daily spending limit for debit card."""
    customer = get_current_customer()
    card = db.session.get(Card, card_id)

    if not card or card.account.customer_id != customer.id:
        flash('Card not found.', 'danger')
        return redirect(url_for('cards.index'))

    limit_str = request.form.get('daily_limit', '').strip()
    try:
        limit_val = Decimal(limit_str)
        if limit_val < Decimal('500.00'):
            flash('Daily limit must be at least ₹500.00.', 'danger')
            return redirect(url_for('cards.index'))
        if limit_val > Decimal('200000.00'):
            flash('Daily limit cannot exceed the maximum cap of ₹2,00,000.00.', 'danger')
            return redirect(url_for('cards.index'))

        card.daily_limit = limit_val
        db.session.commit()
        notify_user(
            customer.user_id,
            'Card Limit Modified',
            f"Daily spending limit for card ending in {card.card_number[-4:]} updated to ₹{limit_val:,.2f}.",
            'INFO'
        )
        flash(f"Daily spending limit updated to ₹{limit_val:,.2f}.", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Invalid limit value: {str(e)}", 'danger')

    return redirect(url_for('cards.index'))


@card_bp.route('/<int:card_id>/set-pin', methods=['POST'])
@login_required
@customer_required
def set_pin(card_id):
    """Change or set 4-digit ATM PIN."""
    customer = get_current_customer()
    card = db.session.get(Card, card_id)

    if not card or card.account.customer_id != customer.id:
        flash('Card not found.', 'danger')
        return redirect(url_for('cards.index'))

    new_pin = request.form.get('new_pin', '').strip()
    confirm_pin = request.form.get('confirm_pin', '').strip()

    if not new_pin or len(new_pin) != 4 or not new_pin.isdigit():
        flash('ATM PIN must be exactly 4 numeric digits.', 'danger')
        return redirect(url_for('cards.index'))

    if new_pin != confirm_pin:
        flash('PIN confirmation does not match.', 'danger')
        return redirect(url_for('cards.index'))

    try:
        card.set_pin(new_pin)
        db.session.commit()
        notify_user(
            customer.user_id,
            'Security Alert: ATM PIN Changed',
            f"The 4-digit ATM PIN for card ending in {card.card_number[-4:]} was changed successfully.",
            'WARNING'
        )
        flash('ATM PIN changed successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to update PIN: {str(e)}", 'danger')

    return redirect(url_for('cards.index'))


@card_bp.route('/<int:card_id>/block', methods=['POST'])
@login_required
@customer_required
def block_card(card_id):
    """Permanently block (hotlist) a lost or stolen card."""
    customer = get_current_customer()
    card = db.session.get(Card, card_id)

    if not card or card.account.customer_id != customer.id:
        flash('Card not found.', 'danger')
        return redirect(url_for('cards.index'))

    try:
        card.status = 'BLOCKED'
        db.session.commit()
        notify_user(
            customer.user_id,
            'Card Permanently Blocked',
            f"Your debit card ending in {card.card_number[-4:]} has been permanently blocked. You can apply for a replacement card anytime.",
            'DANGER'
        )
        flash(f"Card ending in {card.card_number[-4:]} is permanently blocked.", 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to block card: {str(e)}", 'danger')

    return redirect(url_for('cards.index'))


# ====================================================================
# Debit Card Usage Simulators (Online POS & ATM Cash Withdrawal)
# ====================================================================

@card_bp.route('/simulator/pay', methods=['POST'])
@login_required
@customer_required
def simulate_online_payment():
    """Simulate an online E-Commerce / POS card payment transaction."""
    customer = get_current_customer()
    card_number_input = request.form.get('card_number', '').replace(' ', '').strip()
    expiry_month = request.form.get('expiry_month', type=int)
    expiry_year = request.form.get('expiry_year', type=int)
    cvv_input = request.form.get('cvv', '').strip()
    amount_str = request.form.get('amount', '').strip()
    merchant = request.form.get('merchant', 'Online Merchant').strip() or 'Online Merchant'

    # 1. Lookup Card
    card = Card.query.filter_by(card_number=card_number_input).first()
    if not card:
        flash('Payment Declined: Invalid debit card number entered.', 'danger')
        return redirect(url_for('cards.index'))

    # Security check: verify card belongs to current customer
    if card.account.customer_id != customer.id:
        flash('Payment Declined: Card verification failed.', 'danger')
        return redirect(url_for('cards.index'))

    # 2. Check Card Operational Status
    if card.status == 'LOCKED':
        flash('Payment Declined: This card is currently LOCKED. Please unlock it in your card controls.', 'danger')
        return redirect(url_for('cards.index'))

    if card.status == 'BLOCKED':
        flash('Payment Declined: This card is permanently BLOCKED.', 'danger')
        return redirect(url_for('cards.index'))

    # 3. Check Online Channel Permission
    if not card.is_online_enabled:
        flash('Payment Declined: Online / E-commerce usage is disabled for this card. Enable it in card settings.', 'danger')
        return redirect(url_for('cards.index'))

    # 4. Check Expiry Date & CVV
    if card.expiry_month != expiry_month or card.expiry_year != expiry_year:
        flash('Payment Declined: Card expiration date is invalid.', 'danger')
        return redirect(url_for('cards.index'))

    if card.cvv != cvv_input:
        flash('Payment Declined: Invalid CVV security code.', 'danger')
        return redirect(url_for('cards.index'))

    # 5. Check Amount
    try:
        amount = Decimal(amount_str)
        if amount <= Decimal('0.00'):
            flash('Payment Declined: Amount must be strictly greater than zero.', 'danger')
            return redirect(url_for('cards.index'))
    except Exception:
        flash('Payment Declined: Invalid payment amount.', 'danger')
        return redirect(url_for('cards.index'))

    # 6. Check Daily Limit
    spent_today = Decimal(str(card.spent_today))
    daily_cap = Decimal(str(card.daily_limit))
    if spent_today + amount > daily_cap:
        flash(f"Payment Declined: Exceeds daily card spending limit of ₹{daily_cap:,.2f}. Already spent today: ₹{spent_today:,.2f}.", 'danger')
        notify_user(
            customer.user_id,
            'Card Limit Exceeded',
            f"Attempted payment of ₹{amount:,.2f} at {merchant} exceeded your daily card limit of ₹{daily_cap:,.2f}.",
            'WARNING'
        )
        return redirect(url_for('cards.index'))

    # 7. Check Linked Account Balance
    account = card.account
    if account.status != 'ACTIVE':
        flash('Payment Declined: Linked bank account is not active.', 'danger')
        return redirect(url_for('cards.index'))

    curr_balance = Decimal(str(account.balance))
    if amount > curr_balance:
        flash(f"Payment Declined: Insufficient balance in linked account ({account.account_number}). Available: ₹{curr_balance:,.2f}.", 'danger')
        notify_user(
            customer.user_id,
            'Card Transaction Declined',
            f"Card payment of ₹{amount:,.2f} at {merchant} was declined due to insufficient funds.",
            'DANGER'
        )
        return redirect(url_for('cards.index'))

    # 8. ATOMIC CARD PAYMENT EXECUTION
    try:
        account.balance = curr_balance - amount
        new_balance = account.balance
        txn_ref = Transaction.generate_txn_ref(prefix="POS")

        txn = Transaction(
            transaction_ref=txn_ref,
            account_id=account.id,
            card_id=card.id,
            transaction_type='CARD_PAYMENT',
            amount=amount,
            balance_after=new_balance,
            recipient_account=merchant,
            description=f"Debit Card Purchase at {merchant} (Card ending in {card.card_number[-4:]})",
            status='COMPLETED'
        )
        db.session.add(txn)

        notify_user(
            customer.user_id,
            'Debit Card Spent',
            f"₹{amount:,.2f} spent at {merchant} on your card ending in {card.card_number[-4:]}. Remaining account balance: ₹{new_balance:,.2f}. Ref: {txn_ref}",
            'SUCCESS'
        )

        db.session.commit()
        flash(f"Payment of ₹{amount:,.2f} at {merchant} was SUCCESSFUL! (Txn Ref: {txn_ref})", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"Payment transaction failed: {str(e)}", 'danger')

    return redirect(url_for('cards.index'))


@card_bp.route('/simulator/atm', methods=['POST'])
@login_required
@customer_required
def simulate_atm_withdrawal():
    """Simulate an ATM Cash Withdrawal using Debit Card and 4-digit PIN."""
    customer = get_current_customer()
    card_number_input = request.form.get('card_number', '').replace(' ', '').strip()
    pin_input = request.form.get('pin', '').strip()
    amount_str = request.form.get('amount', '').strip()

    # 1. Lookup Card
    card = Card.query.filter_by(card_number=card_number_input).first()
    if not card or card.account.customer_id != customer.id:
        flash('ATM Transaction Cancelled: Invalid debit card.', 'danger')
        return redirect(url_for('cards.index'))

    # 2. Check Status
    if card.status == 'LOCKED':
        flash('ATM Transaction Cancelled: This card is locked. Please unlock it to perform ATM transactions.', 'danger')
        return redirect(url_for('cards.index'))

    if card.status == 'BLOCKED':
        flash('ATM Transaction Cancelled: This card is permanently blocked.', 'danger')
        return redirect(url_for('cards.index'))

    # 3. Check PIN
    if not card.check_pin(pin_input):
        flash('ATM Transaction Cancelled: Incorrect 4-digit ATM PIN entered.', 'danger')
        notify_user(
            customer.user_id,
            'Security Warning: Incorrect ATM PIN',
            f"An incorrect ATM PIN was entered for debit card ending in {card.card_number[-4:]}.",
            'WARNING'
        )
        return redirect(url_for('cards.index'))

    # 4. Check Amount
    try:
        amount = Decimal(amount_str)
        if amount <= Decimal('0.00'):
            flash('ATM Transaction Cancelled: Withdrawal amount must be positive.', 'danger')
            return redirect(url_for('cards.index'))
    except Exception:
        flash('ATM Transaction Cancelled: Invalid amount.', 'danger')
        return redirect(url_for('cards.index'))

    # 5. Check Daily Limit
    spent_today = Decimal(str(card.spent_today))
    daily_cap = Decimal(str(card.daily_limit))
    if spent_today + amount > daily_cap:
        flash(f"ATM Transaction Cancelled: Exceeds daily card limit of ₹{daily_cap:,.2f}.", 'danger')
        return redirect(url_for('cards.index'))

    # 6. Check Account Balance
    account = card.account
    curr_balance = Decimal(str(account.balance))
    if amount > curr_balance:
        flash(f"ATM Transaction Cancelled: Insufficient balance. Available: ₹{curr_balance:,.2f}.", 'danger')
        return redirect(url_for('cards.index'))

    # 7. Execute ATM Withdrawal
    try:
        account.balance = curr_balance - amount
        new_balance = account.balance
        txn_ref = Transaction.generate_txn_ref(prefix="ATM")

        txn = Transaction(
            transaction_ref=txn_ref,
            account_id=account.id,
            card_id=card.id,
            transaction_type='ATM_WITHDRAWAL',
            amount=amount,
            balance_after=new_balance,
            recipient_account='SmartBank ATM Cash Dispenser',
            description=f"ATM Cash Withdrawal with Card ending in {card.card_number[-4:]}",
            status='COMPLETED'
        )
        db.session.add(txn)

        notify_user(
            customer.user_id,
            'ATM Cash Withdrawn',
            f"₹{amount:,.2f} dispensed via ATM using debit card ending in {card.card_number[-4:]}. New balance: ₹{new_balance:,.2f}. Ref: {txn_ref}",
            'INFO'
        )

        db.session.commit()
        flash(f"ATM Cash Dispensed: ₹{amount:,.2f} withdrawn successfully! (Txn Ref: {txn_ref})", 'success')

    except Exception as e:
        db.session.rollback()
        flash(f"ATM transaction failed: {str(e)}", 'danger')

    return redirect(url_for('cards.index'))
