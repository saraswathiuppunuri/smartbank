import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smartbank-super-secret-key-2026-btech-cse')
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database connection parameters
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '3306')
    DB_NAME = os.environ.get('DB_NAME', 'smartbank_db')
    
    # Priority: explicit DATABASE_URL -> constructed MySQL URL -> SQLite fallback
    if os.environ.get('DATABASE_URL'):
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }
    
    # Pagination
    ITEMS_PER_PAGE = 10
    
    # Application Settings
    BANK_NAME = "SmartBank"
    BANK_CODE = "SMRT"
    DEFAULT_IFSC = "SMRT0001001"
    MINIMUM_BALANCE = 500.00
    LOW_BALANCE_THRESHOLD = 1000.00


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'


class ProductionConfig(Config):
    DEBUG = False
    # In production, require secure cookie
    SESSION_COOKIE_SECURE = True


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
