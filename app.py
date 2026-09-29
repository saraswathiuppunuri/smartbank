import os
from datetime import datetime, timezone
from flask import Flask, render_template, redirect, url_for, session, jsonify, request
from config import config_by_name
from models import db, User, Customer, Account, Card, Transaction, Beneficiary, Notification
from routes import auth_bp, customer_bp, admin_bp, transaction_bp, card_bp, api_bp
from routes.helpers import get_current_user

def create_app(config_name=None):
    """Application Factory for SmartBank."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Initialize extensions
    db.init_app(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(transaction_bp)
    app.register_blueprint(card_bp)
    app.register_blueprint(api_bp)

    # Root redirect
    @app.route('/')
    def index():
        current_user = get_current_user()
        if current_user:
            if current_user.is_admin:
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('customer.dashboard'))
        return redirect(url_for('auth.login'))

    # Jinja Context Processors & Filters
    @app.context_processor
    def inject_global_vars():
        user = get_current_user()
        unread_count = 0
        if user:
            unread_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
        return {
            'current_user': user,
            'unread_notifications_count': unread_count,
            'current_year': datetime.now(timezone.utc).year,
            'bank_name': app.config.get('BANK_NAME', 'SmartBank')
        }

    @app.template_filter('currency')
    def currency_filter(val):
        """Format number as currency: ₹12,345.67"""
        try:
            return f"₹{float(val):,.2f}"
        except (ValueError, TypeError):
            return "₹0.00"

    @app.template_filter('datetime_format')
    def datetime_format(val, fmt='%d %b %Y, %I:%M %p'):
        """Format datetime object into readable string."""
        if not val:
            return ""
        if isinstance(val, str):
            try:
                val = datetime.fromisoformat(val)
            except Exception:
                return val
        return val.strftime(fmt)

    # Custom Error Handlers
    @app.errorhandler(400)
    def bad_request_error(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Bad Request', 'error': str(e)}), 400
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden_error(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Access Forbidden', 'error': str(e)}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(e):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Resource Not Found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Internal Server Error'}), 500
        return render_template('errors/500.html'), 500

    # CLI command to initialize database tables
    @app.cli.command('init-db')
    def init_db():
        """Create database tables."""
        with app.app_context():
            db.create_all()
            print("Successfully initialized all database tables.")

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = bool(int(os.environ.get('FLASK_DEBUG', 1)))
    print(f"Starting SmartBank application server on http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
