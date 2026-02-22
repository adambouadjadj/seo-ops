import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from seo-ops/ root
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / '.env')


class BaseConfig:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    WTF_CSRF_HEADERS = ['X-CSRFToken', 'X-CSRF-Token']


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR / "instance" / "seo_ops.db"}'
    )
    # Resolve sqlite relative path to absolute
    _db_url = SQLALCHEMY_DATABASE_URI
    if _db_url and _db_url.startswith('sqlite:///') and not _db_url.startswith('sqlite:////'):
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{BASE_DIR / "instance" / "seo_ops.db"}'


class ProductionConfig(BaseConfig):
    DEBUG = False
    SECRET_KEY = os.environ['SECRET_KEY']  # Raises KeyError at startup if not set — intentional
    SQLALCHEMY_DATABASE_URI = os.environ['DATABASE_URL']  # Same — must be explicit in production


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
}
