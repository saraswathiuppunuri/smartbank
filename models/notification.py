from datetime import datetime, timezone
from models import db

class Notification(db.Model):
    """Notification alerts for account and transaction activities."""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), nullable=False, default='INFO')  # INFO, SUCCESS, WARNING, DANGER
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = db.relationship('User', back_populates='notifications')

    @property
    def badge_class(self):
        mapping = {
            'INFO': 'bg-info text-dark',
            'SUCCESS': 'bg-success text-white',
            'WARNING': 'bg-warning text-dark',
            'DANGER': 'bg-danger text-white'
        }
        return mapping.get(self.type, 'bg-secondary')

    @property
    def icon_class(self):
        mapping = {
            'INFO': 'bi-info-circle-fill text-info',
            'SUCCESS': 'bi-check-circle-fill text-success',
            'WARNING': 'bi-exclamation-triangle-fill text-warning',
            'DANGER': 'bi-x-circle-fill text-danger'
        }
        return mapping.get(self.type, 'bi-bell-fill text-secondary')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'type': self.type,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<Notification {self.title} ({self.type})>"
