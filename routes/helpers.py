from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
from models import db, User, Customer, Notification

def get_current_user():
    """Retrieve currently authenticated user object from session, or None."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        session.clear()
        return None
    return user

def get_current_customer():
    """Retrieve Customer profile associated with current user."""
    user = get_current_user()
    if not user or user.role != 'customer':
        return None
    return user.customer

def login_required(f):
    """Decorator ensuring user is authenticated and active."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Authentication required. Please log in.'}), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        
        user = db.session.get(User, user_id)
        if not user or not user.is_active:
            session.clear()
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Account is inactive or disabled. Contact administrator.'}), 403
            flash('Your account has been deactivated. Please contact support.', 'danger')
            return redirect(url_for('auth.login'))
            
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator ensuring user is authenticated with admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        role = session.get('role')
        if not user_id or role != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Administrative privileges required.'}), 403
            flash('Unauthorized access: Administrator credentials required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def customer_required(f):
    """Decorator ensuring user is authenticated with customer role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        role = session.get('role')
        if not user_id or role != 'customer':
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Customer credentials required.'}), 403
            flash('This section is reserved for SmartBank customers.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def notify_user(user_id, title, message, notif_type='INFO'):
    """Create a persistent notification record for a user."""
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notif_type
        )
        db.session.add(notif)
        db.session.commit()
        return notif
    except Exception as e:
        db.session.rollback()
        return None
