import re
from decimal import Decimal
from flask import Blueprint, request, jsonify, session
from models import db, User, Customer, Account, Card, Transaction, Beneficiary, Notification
from routes.helpers import get_current_user, login_required, admin_required, notify_user

api_bp = Blueprint('api', __name__, url_prefix='/api')

def api_response(success=True, message="", data=None, status_code=200):
    """Standardized JSON response envelope."""
    payload = {
        'success': success,
        'message': message,
        'data': data
    }
    return jsonify(payload), status_code

# --- Authentication Endpoints ---

@api_bp.route('/login', methods=['POST'])
def api_login():
    """API Login endpoint returning session confirmation and user profile."""
    data = request.get_json(silent=True) or request.form
    identifier = data.get('identifier', '').strip()
    password = data.get('password', '').strip()

    if not identifier or not password:
        return api_response(False, "Username/email and password are required.", status_code=400)

    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
    if not user or not user.check_password(password):
        return api_response(False, "Invalid username/email or password.", status_code=401)

    if not user.is_active:
        return api_response(False, "Your account has been deactivated.", status_code=403)

    session.clear()
    session['user_id'] = user.id
    session['username'] = user.username
    session['role'] = user.role
    session['email'] = user.email

    user_data = user.to_dict()
    if user.role == 'customer' and user.customer:
        session['customer_id'] = user.customer.id
        session['customer_name'] = user.customer.full_name
        user_data['customer'] = user.customer.to_dict()

    return api_response(True, "Login successful.", user_data, 200)


@api_bp.route('/register', methods=['POST'])
def api_register():
    """API Register endpoint to register new customer and primary account."""
    data = request.get_json(silent=True) or request.form
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    phone = data.get('phone', '').strip()
    account_type = data.get('account_type', 'Savings')
    initial_deposit_val = data.get('initial_deposit', 0)

    if not username or not email or not password or not first_name or not last_name or not phone:
        return api_response(False, "All core profile fields are required.", status_code=400)

    if User.query.filter_by(username=username).first():
        return api_response(False, "Username already registered.", status_code=409)

    if User.query.filter_by(email=email).first():
        return api_response(False, "Email already registered.", status_code=409)

    try:
        initial_deposit = Decimal(str(initial_deposit_val))
        if initial_deposit < 0:
            return api_response(False, "Initial deposit cannot be negative.", status_code=400)
    except Exception:
        return api_response(False, "Invalid initial deposit amount.", status_code=400)

    try:
        user = User(username=username, email=email, role='customer', is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        customer = Customer(
            user_id=user.id,
            customer_code=Customer.generate_customer_code(),
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            address=data.get('address', ''),
            city=data.get('city', ''),
            state=data.get('state', ''),
            pincode=data.get('pincode', '')
        )
        db.session.add(customer)
        db.session.flush()

        account = Account(
            customer_id=customer.id,
            account_number=Account.generate_account_number(),
            account_type=account_type if account_type in ['Savings', 'Current', 'Salary'] else 'Savings',
            balance=initial_deposit,
            status='ACTIVE'
        )
        db.session.add(account)
        db.session.flush()

        if initial_deposit > 0:
            txn = Transaction(
                transaction_ref=Transaction.generate_txn_ref(),
                account_id=account.id,
                transaction_type='DEPOSIT',
                amount=initial_deposit,
                balance_after=initial_deposit,
                description='API Initial Account Opening Deposit',
                status='COMPLETED'
            )
            db.session.add(txn)

        notify_user(
            user.id,
            'Welcome to SmartBank!',
            f"Your account {account.account_number} was created successfully.",
            'SUCCESS'
        )

        db.session.commit()

        return api_response(True, "Customer registered successfully.", {
            'user': user.to_dict(),
            'customer': customer.to_dict(),
            'account': account.to_dict()
        }, 201)

    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Registration failed: {str(e)}", status_code=500)


# --- Customer Endpoints ---

@api_bp.route('/customers', methods=['GET'])
@login_required
@admin_required
def api_get_customers():
    """Admin endpoint to list all customers."""
    customers = Customer.query.all()
    return api_response(True, "Customers retrieved.", [c.to_dict() for c in customers])


@api_bp.route('/customers/<int:customer_id>', methods=['GET'])
@login_required
def api_get_customer(customer_id):
    """Retrieve details of a specific customer."""
    current_user = get_current_user()
    customer = db.session.get(Customer, customer_id)
    if not customer:
        return api_response(False, "Customer not found.", status_code=404)

    # Allow if admin or current customer
    if current_user.role != 'admin' and current_user.id != customer.user_id:
        return api_response(False, "Access forbidden.", status_code=403)

    data = customer.to_dict()
    data['accounts'] = [acc.to_dict() for acc in customer.accounts]
    return api_response(True, "Customer profile retrieved.", data)


@api_bp.route('/customers/<int:customer_id>', methods=['PUT'])
@login_required
def api_update_customer(customer_id):
    """Update customer profile information."""
    current_user = get_current_user()
    customer = db.session.get(Customer, customer_id)
    if not customer:
        return api_response(False, "Customer not found.", status_code=404)

    if current_user.role != 'admin' and current_user.id != customer.user_id:
        return api_response(False, "Access forbidden.", status_code=403)

    data = request.get_json(silent=True) or request.form
    try:
        if 'first_name' in data:
            customer.first_name = data['first_name']
        if 'last_name' in data:
            customer.last_name = data['last_name']
        if 'phone' in data:
            customer.phone = data['phone']
        if 'address' in data:
            customer.address = data['address']
        if 'city' in data:
            customer.city = data['city']
        if 'state' in data:
            customer.state = data['state']
        if 'pincode' in data:
            customer.pincode = data['pincode']

        if 'email' in data and data['email'] != customer.user.email:
            existing = User.query.filter_by(email=data['email']).first()
            if existing and existing.id != customer.user_id:
                return api_response(False, "Email already in use.", status_code=409)
            customer.user.email = data['email']

        db.session.commit()
        return api_response(True, "Customer profile updated.", customer.to_dict())
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Update failed: {str(e)}", status_code=500)


@api_bp.route('/customers/<int:customer_id>', methods=['DELETE'])
@login_required
@admin_required
def api_delete_customer(customer_id):
    """Soft-delete/deactivate customer."""
    customer = db.session.get(Customer, customer_id)
    if not customer:
        return api_response(False, "Customer not found.", status_code=404)

    customer.user.is_active = False
    for acc in customer.accounts:
        acc.status = 'INACTIVE'

    db.session.commit()
    return api_response(True, f"Customer {customer.customer_code} deactivated successfully.")


# --- Account Endpoints ---

@api_bp.route('/accounts', methods=['GET'])
@login_required
def api_get_accounts():
    """Retrieve accounts for logged-in customer or all accounts for admin."""
    current_user = get_current_user()
    if current_user.is_admin:
        accounts = Account.query.all()
    else:
        accounts = current_user.customer.accounts.all()

    return api_response(True, "Accounts retrieved.", [acc.to_dict() for acc in accounts])


@api_bp.route('/accounts/<int:account_id>', methods=['GET'])
@login_required
def api_get_account(account_id):
    """Retrieve single account details."""
    current_user = get_current_user()
    account = db.session.get(Account, account_id)
    if not account:
        return api_response(False, "Account not found.", status_code=404)

    if not current_user.is_admin and account.customer_id != current_user.customer.id:
        return api_response(False, "Access forbidden.", status_code=403)

    return api_response(True, "Account details retrieved.", account.to_dict())


# --- Transaction API Endpoints ---

@api_bp.route('/deposit', methods=['POST'])
@login_required
def api_deposit():
    """Deposit money into account."""
    data = request.get_json(silent=True) or request.form
    account_number = data.get('account_number')
    amount_val = data.get('amount')
    description = data.get('description', 'API Deposit')

    current_user = get_current_user()
    account = Account.query.filter_by(account_number=account_number).first()
    if not account:
        return api_response(False, "Account not found.", status_code=404)

    if not current_user.is_admin and account.customer_id != current_user.customer.id:
        return api_response(False, "Access denied to deposit in this account.", status_code=403)

    if account.status != 'ACTIVE':
        return api_response(False, "Account is not active.", status_code=400)

    try:
        amount = Decimal(str(amount_val))
        if amount <= 0:
            return api_response(False, "Deposit amount must be positive.", status_code=400)
    except Exception:
        return api_response(False, "Invalid amount value.", status_code=400)

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
            description=description,
            status='COMPLETED'
        )
        db.session.add(txn)
        notify_user(
            account.customer.user_id,
            'Deposit Received',
            f"₹{amount:,.2f} deposited into account {account.account_number}. Balance: ₹{new_balance:,.2f}.",
            'SUCCESS'
        )
        db.session.commit()

        return api_response(True, "Deposit completed successfully.", {
            'transaction': txn.to_dict(),
            'account': account.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Deposit failed: {str(e)}", status_code=500)


@api_bp.route('/withdraw', methods=['POST'])
@login_required
def api_withdraw():
    """Withdraw funds from account."""
    data = request.get_json(silent=True) or request.form
    account_number = data.get('account_number')
    amount_val = data.get('amount')
    description = data.get('description', 'API Withdrawal')

    current_user = get_current_user()
    account = Account.query.filter_by(account_number=account_number).first()
    if not account:
        return api_response(False, "Account not found.", status_code=404)

    if not current_user.is_admin and account.customer_id != current_user.customer.id:
        return api_response(False, "Access denied to withdraw from this account.", status_code=403)

    if account.status != 'ACTIVE':
        return api_response(False, "Account is not active.", status_code=400)

    try:
        amount = Decimal(str(amount_val))
        if amount <= 0:
            return api_response(False, "Withdrawal amount must be positive.", status_code=400)
    except Exception:
        return api_response(False, "Invalid amount value.", status_code=400)

    current_balance = Decimal(str(account.balance))
    if amount > current_balance:
        return api_response(False, f"Insufficient balance. Current balance is ₹{current_balance:,.2f}.", status_code=400)

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
            description=description,
            status='COMPLETED'
        )
        db.session.add(txn)
        notify_user(
            account.customer.user_id,
            'Withdrawal Processed',
            f"₹{amount:,.2f} withdrawn from account {account.account_number}. Balance: ₹{new_balance:,.2f}.",
            'INFO'
        )
        db.session.commit()

        return api_response(True, "Withdrawal successful.", {
            'transaction': txn.to_dict(),
            'account': account.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Withdrawal failed: {str(e)}", status_code=500)


@api_bp.route('/transfer', methods=['POST'])
@login_required
def api_transfer():
    """Transfer funds atomically between accounts."""
    data = request.get_json(silent=True) or request.form
    sender_acc_num = data.get('sender_account')
    recipient_acc_num = data.get('recipient_account')
    amount_val = data.get('amount')
    description = data.get('description', 'API Fund Transfer')

    current_user = get_current_user()

    sender_account = Account.query.filter_by(account_number=sender_acc_num).first()
    if not sender_account:
        return api_response(False, "Sender account not found.", status_code=404)

    if not current_user.is_admin and sender_account.customer_id != current_user.customer.id:
        return api_response(False, "Unauthorized source account.", status_code=403)

    if sender_account.status != 'ACTIVE':
        return api_response(False, "Sender account is not active.", status_code=400)

    if sender_acc_num == recipient_acc_num:
        return api_response(False, "Cannot transfer funds to identical account.", status_code=400)

    recipient_account = Account.query.filter_by(account_number=recipient_acc_num).first()
    if not recipient_account:
        return api_response(False, "Recipient account not found.", status_code=404)

    if recipient_account.status != 'ACTIVE':
        return api_response(False, "Recipient account is inactive.", status_code=400)

    try:
        amount = Decimal(str(amount_val))
        if amount <= 0:
            return api_response(False, "Transfer amount must be positive.", status_code=400)
    except Exception:
        return api_response(False, "Invalid amount value.", status_code=400)

    sender_balance = Decimal(str(sender_account.balance))
    if amount > sender_balance:
        return api_response(False, "Insufficient balance.", status_code=400)

    try:
        sender_account.balance = sender_balance - amount
        recipient_account.balance = Decimal(str(recipient_account.balance)) + amount

        txn_ref = Transaction.generate_txn_ref(prefix="TRF")

        sender_txn = Transaction(
            transaction_ref=txn_ref,
            account_id=sender_account.id,
            transaction_type='TRANSFER_SENT',
            amount=amount,
            balance_after=sender_account.balance,
            recipient_account=recipient_acc_num,
            description=description,
            status='COMPLETED'
        )
        db.session.add(sender_txn)

        recipient_txn = Transaction(
            transaction_ref=f"{txn_ref}-R",
            account_id=recipient_account.id,
            transaction_type='TRANSFER_RECEIVED',
            amount=amount,
            balance_after=recipient_account.balance,
            recipient_account=sender_acc_num,
            description=description,
            status='COMPLETED'
        )
        db.session.add(recipient_txn)

        notify_user(
            sender_account.customer.user_id,
            'Fund Transfer Sent',
            f"₹{amount:,.2f} sent to {recipient_acc_num}.",
            'SUCCESS'
        )
        notify_user(
            recipient_account.customer.user_id,
            'Fund Transfer Received',
            f"₹{amount:,.2f} received from {sender_acc_num}.",
            'SUCCESS'
        )

        db.session.commit()
        return api_response(True, "Transfer completed successfully.", {
            'reference_id': txn_ref,
            'amount': float(amount),
            'sender_balance': float(sender_account.balance)
        })
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Transfer failed: {str(e)}", status_code=500)


# --- Transaction Retrieval Endpoints ---

@api_bp.route('/transactions', methods=['GET'])
@login_required
def api_get_transactions():
    """Retrieve transactions with filtering."""
    current_user = get_current_user()
    if current_user.is_admin:
        query = Transaction.query
    else:
        acc_ids = [acc.id for acc in current_user.customer.accounts]
        query = Transaction.query.filter(Transaction.account_id.in_(acc_ids))

    txn_type = request.args.get('type')
    if txn_type:
        query = query.filter_by(transaction_type=txn_type.upper())

    txns = query.order_by(Transaction.created_at.desc()).limit(50).all()
    return api_response(True, "Transactions retrieved.", [t.to_dict() for t in txns])


@api_bp.route('/transactions/<int:txn_id>', methods=['GET'])
@login_required
def api_get_transaction_by_id(txn_id):
    """Retrieve single transaction details."""
    current_user = get_current_user()
    txn = db.session.get(Transaction, txn_id)
    if not txn:
        return api_response(False, "Transaction record not found.", status_code=404)

    if not current_user.is_admin and txn.account.customer_id != current_user.customer.id:
        return api_response(False, "Access forbidden.", status_code=403)

    return api_response(True, "Transaction record retrieved.", txn.to_dict())


# --- Beneficiary Endpoints ---

@api_bp.route('/beneficiaries', methods=['GET', 'POST'])
@login_required
def api_beneficiaries():
    """List or create beneficiaries for the current customer."""
    current_user = get_current_user()
    if not current_user.customer:
        return api_response(False, "Customer account required.", status_code=400)

    customer = current_user.customer

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        name = data.get('name', '').strip()
        account_number = data.get('account_number', '').strip()
        bank_name = data.get('bank_name', 'SmartBank').strip()
        ifsc_code = data.get('ifsc_code', 'SMRT0001001').strip().upper()

        if not name or not account_number or not ifsc_code:
            return api_response(False, "Name, account number, and IFSC code are required.", status_code=400)

        existing = Beneficiary.query.filter_by(customer_id=customer.id, account_number=account_number).first()
        if existing:
            return api_response(False, "Beneficiary account already saved.", status_code=409)

        beneficiary = Beneficiary(
            customer_id=customer.id,
            name=name,
            account_number=account_number,
            bank_name=bank_name,
            ifsc_code=ifsc_code,
            email=data.get('email', '')
        )
        db.session.add(beneficiary)
        db.session.commit()

        return api_response(True, "Beneficiary saved successfully.", beneficiary.to_dict(), 201)

    beneficiaries = customer.beneficiaries.all()
    return api_response(True, "Beneficiaries list retrieved.", [b.to_dict() for b in beneficiaries])


@api_bp.route('/beneficiaries/<int:ben_id>', methods=['PUT', 'DELETE'])
@login_required
def api_single_beneficiary(ben_id):
    """Update or delete a saved beneficiary."""
    current_user = get_current_user()
    if not current_user.customer:
        return api_response(False, "Customer account required.", status_code=400)

    beneficiary = Beneficiary.query.filter_by(id=ben_id, customer_id=current_user.customer.id).first()
    if not beneficiary:
        return api_response(False, "Beneficiary not found.", status_code=404)

    if request.method == 'DELETE':
        db.session.delete(beneficiary)
        db.session.commit()
        return api_response(True, "Beneficiary deleted successfully.")

    data = request.get_json(silent=True) or request.form
    if 'name' in data:
        beneficiary.name = data['name']
    if 'bank_name' in data:
        beneficiary.bank_name = data['bank_name']
    if 'ifsc_code' in data:
        beneficiary.ifsc_code = data['ifsc_code']
    if 'email' in data:
        beneficiary.email = data['email']

    db.session.commit()
    return api_response(True, "Beneficiary updated successfully.", beneficiary.to_dict())


# --- Debit Card Endpoints ---

@api_bp.route('/cards', methods=['GET'])
@login_required
def api_get_cards():
    """Retrieve all debit cards for customer or all cards for admin."""
    current_user = get_current_user()
    if current_user.is_admin:
        cards = Card.query.all()
    else:
        if not current_user.customer:
            return api_response(False, "Customer profile required.", status_code=400)
        account_ids = [acc.id for acc in current_user.customer.accounts]
        cards = Card.query.filter(Card.account_id.in_(account_ids)).all()

    return api_response(True, "Debit cards retrieved.", [c.to_dict(include_sensitive=False) for c in cards])


@api_bp.route('/cards/<int:card_id>', methods=['GET'])
@login_required
def api_get_card(card_id):
    """Retrieve single card details."""
    current_user = get_current_user()
    card = db.session.get(Card, card_id)
    if not card:
        return api_response(False, "Debit card not found.", status_code=404)

    is_owner = current_user.customer and card.account.customer_id == current_user.customer.id
    if not current_user.is_admin and not is_owner:
        return api_response(False, "Access forbidden.", status_code=403)

    return api_response(True, "Card details retrieved.", card.to_dict(include_sensitive=is_owner))


@api_bp.route('/cards/apply', methods=['POST'])
@login_required
def api_apply_card():
    """Apply and issue a new debit card linked to an active account."""
    current_user = get_current_user()
    if not current_user.customer:
        return api_response(False, "Customer account required.", status_code=400)

    data = request.get_json(silent=True) or request.form
    account_number = data.get('account_number')
    card_network = data.get('card_network', 'VISA').strip().upper()
    card_type = data.get('card_type', 'Platinum').strip()
    pin = str(data.get('pin', '')).strip()

    account = Account.query.filter_by(account_number=account_number, customer_id=current_user.customer.id).first()
    if not account:
        return api_response(False, "Account not found or access denied.", status_code=404)

    if account.status != 'ACTIVE':
        return api_response(False, "Account is not active.", status_code=400)

    if not pin or len(pin) != 4 or not pin.isdigit():
        return api_response(False, "PIN must be exactly 4 numeric digits.", status_code=400)

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    card_num = Card.generate_card_number(network=card_network)
    cvv = Card.generate_cvv()

    try:
        new_card = Card(
            account_id=account.id,
            card_number=card_num,
            card_holder_name=current_user.customer.full_name.upper(),
            card_network=card_network if card_network in ['VISA', 'MASTERCARD', 'RUPAY'] else 'VISA',
            card_type=card_type if card_type in ['Platinum', 'Classic', 'Business'] else 'Platinum',
            expiry_month=now.month,
            expiry_year=now.year + 5,
            cvv=cvv,
            daily_limit=Decimal('50000.00'),
            status='ACTIVE'
        )
        new_card.set_pin(pin)
        db.session.add(new_card)

        notify_user(
            current_user.id,
            'New Debit Card Issued',
            f"Your new {new_card.card_network} Debit Card ending in {card_num[-4:]} has been activated.",
            'SUCCESS'
        )
        db.session.commit()

        return api_response(True, "Debit card issued successfully.", new_card.to_dict(include_sensitive=True), 201)
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Card issuance failed: {str(e)}", status_code=500)


@api_bp.route('/cards/<int:card_id>/toggle-lock', methods=['POST'])
@login_required
def api_toggle_card_lock(card_id):
    """Lock or unlock a debit card."""
    current_user = get_current_user()
    card = db.session.get(Card, card_id)
    if not card:
        return api_response(False, "Card not found.", status_code=404)

    if not current_user.is_admin and (not current_user.customer or card.account.customer_id != current_user.customer.id):
        return api_response(False, "Access forbidden.", status_code=403)

    if card.is_blocked:
        return api_response(False, "Card is permanently blocked and cannot be unlocked.", status_code=400)

    card.status = 'LOCKED' if card.is_active else 'ACTIVE'
    db.session.commit()
    return api_response(True, f"Card status updated to {card.status}.", {'card_id': card.id, 'status': card.status})


@api_bp.route('/cards/pay', methods=['POST'])
@login_required
def api_card_pay():
    """Process a debit card POS / E-Commerce payment."""
    data = request.get_json(silent=True) or request.form
    card_number = str(data.get('card_number', '')).replace(' ', '').strip()
    expiry_month = int(data.get('expiry_month', 0))
    expiry_year = int(data.get('expiry_year', 0))
    cvv = str(data.get('cvv', '')).strip()
    amount_val = data.get('amount')
    merchant = data.get('merchant', 'Online Merchant').strip() or 'Online Merchant'

    card = Card.query.filter_by(card_number=card_number).first()
    if not card:
        return api_response(False, "Payment Declined: Invalid card number.", status_code=404)

    if card.status == 'LOCKED':
        return api_response(False, "Payment Declined: Card is LOCKED.", status_code=400)
    if card.status == 'BLOCKED':
        return api_response(False, "Payment Declined: Card is BLOCKED.", status_code=400)

    if not card.is_online_enabled:
        return api_response(False, "Payment Declined: Online transactions disabled on this card.", status_code=400)

    if card.expiry_month != expiry_month or card.expiry_year != expiry_year:
        return api_response(False, "Payment Declined: Expiration date invalid.", status_code=400)

    if card.cvv != cvv:
        return api_response(False, "Payment Declined: Incorrect CVV security code.", status_code=400)

    try:
        amount = Decimal(str(amount_val))
        if amount <= 0:
            return api_response(False, "Amount must be positive.", status_code=400)
    except Exception:
        return api_response(False, "Invalid amount value.", status_code=400)

    spent_today = Decimal(str(card.spent_today))
    daily_cap = Decimal(str(card.daily_limit))
    if spent_today + amount > daily_cap:
        return api_response(False, f"Payment Declined: Exceeds daily card limit of ₹{daily_cap:,.2f}.", status_code=400)

    account = card.account
    if account.status != 'ACTIVE':
        return api_response(False, "Payment Declined: Linked account is inactive.", status_code=400)

    curr_balance = Decimal(str(account.balance))
    if amount > curr_balance:
        return api_response(False, "Payment Declined: Insufficient balance.", status_code=400)

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
            account.customer.user_id,
            'Debit Card Spent',
            f"₹{amount:,.2f} spent at {merchant} on card ending in {card.card_number[-4:]}. Ref: {txn_ref}",
            'SUCCESS'
        )
        db.session.commit()

        return api_response(True, "Card payment successful.", {
            'reference_id': txn_ref,
            'amount': float(amount),
            'merchant': merchant,
            'remaining_balance': float(new_balance),
            'card_last4': card.card_number[-4:]
        })
    except Exception as e:
        db.session.rollback()
        return api_response(False, f"Transaction failed: {str(e)}", status_code=500)

