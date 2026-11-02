import os
import sys
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Enable PyMySQL as MySQLdb driver fallback if mysqlclient is not compiled
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / '.env')

# Security & Environment Configuration
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-entenaadu-village-app-development-secret-key-change-in-prod'
    else:
        raise ValueError("CRITICAL SECURITY ERROR: SECRET_KEY environment variable is not set in production!")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,.onrender.com').split(',')
    if host.strip()
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party packages
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',

    # Ente Naadu Apps
    'apps.accounts',
    'apps.shops',
    'apps.orders',
    'apps.events',
    'apps.complaints',
    'apps.directory',
    'apps.ai_assistant',
    'apps.chat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Serves static files on Render
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'entenaadu.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.orders.context_processors.cart_context',
                'apps.chat.context_processors.chat_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'entenaadu.wsgi.application'
ASGI_APPLICATION = 'entenaadu.asgi.application'

# Database Configuration (PostgreSQL / MySQL / SQLite)
# Defaults to SQLite locally if DATABASE_URL is not set
default_db_url = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
database_url = os.environ.get('DATABASE_URL', default_db_url)

db_config = dj_database_url.config(
    default=database_url,
    conn_max_age=int(os.environ.get('DB_CONN_MAX_AGE', '600')),
    ssl_require=database_url.startswith('postgres') and not DEBUG
)

# MySQL Production Configuration: utf8mb4 charset for Malayalam text & strict mode
if 'mysql' in db_config.get('ENGINE', ''):
    db_config.setdefault('OPTIONS', {})
    db_config['OPTIONS'].update({
        'charset': 'utf8mb4',
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION', NAMES utf8mb4 COLLATE utf8mb4_unicode_ci",
    })
    mysql_ssl_ca = os.environ.get('MYSQL_SSL_CA')
    if mysql_ssl_ca and os.path.exists(mysql_ssl_ca):
        db_config['OPTIONS']['ssl'] = {'ca': mysql_ssl_ca}

DATABASES = {
    'default': db_config
}

# Custom User Model (Phone Number based authentication)
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6}, # Convenient 6-character min for local community users
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata' # IST for Kerala / India
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
# Create static and staticfiles directories if they don't exist
os.makedirs(BASE_DIR / 'static', exist_ok=True)
os.makedirs(STATIC_ROOT, exist_ok=True)

# Whitenoise compression and caching for production on Render
# In test environments, use standard StaticFilesStorage to avoid requiring a pre-generated manifest
IS_TESTING = 'test' in sys.argv

# Media files and Cloud Storage
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
os.makedirs(MEDIA_ROOT, exist_ok=True)

USE_S3 = os.environ.get('USE_S3', 'False').lower() in ('true', '1', 'yes') or bool(os.environ.get('AWS_STORAGE_BUCKET_NAME'))
default_storage_backend = "django.core.files.storage.FileSystemStorage"

if USE_S3:
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'ap-south-1') # Mumbai region for India
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL') # Cloudflare R2 / MinIO support
    AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN')
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = False
    default_storage_backend = "storages.backends.s3boto3.S3Boto3Storage"

STORAGES = {
    "default": {
        "BACKEND": default_storage_backend,
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if IS_TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# Prevent MissingFileError from breaking production if an unmanifested asset is referenced
WHITENOISE_MANIFEST_STRICT = False

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/auth/login/'

# Django REST Framework Configuration
REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'apps.common.exceptions.custom_exception_handler',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '300/minute',
        'auth': '10/minute',
        'ai_assistant': '15/minute',
    },
}

# CORS Configuration (Allows Flutter Web and Mobile API calls)
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all only in local debug mode
cors_origins_env = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if cors_origins_env:
    CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_origins_env.split(',') if origin.strip()]

# CSRF Trusted Origins (Required for Django 4.0+ POST requests from web & local dev)
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1',
    'http://localhost',
    'https://*.onrender.com',
]
csrf_origins_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS.extend([origin.strip() for origin in csrf_origins_env.split(',') if origin.strip()])

# Session & Cookie Configuration (Collision-Free & Isolated)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 14 days (2 weeks)
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_NAME = 'entenaadu_sessionid'
SESSION_COOKIE_SECURE = not DEBUG

CSRF_COOKIE_AGE = 1209600  # 14 days
CSRF_COOKIE_HTTPONLY = False  # Allows JavaScript/AJAX to read CSRF token
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_NAME = 'entenaadu_csrftoken'
CSRF_COOKIE_SECURE = not DEBUG
CSRF_USE_SESSIONS = False  # Use cookie-based CSRF storage

# Custom CSRF Failure Handler (Friendly redirect instead of raw 403)
CSRF_FAILURE_VIEW = 'entenaadu.views.csrf_failure_view'

# Production Security Headers
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # Can be disabled via env if reverse proxy (e.g. Nginx or Cloudflare) handles SSL termination
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() in ('true', '1', 'yes')

# Sentry Error Monitoring & Performance APM
SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN and not IS_TESTING:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.2')),
            send_default_pii=False, # Protect citizen PII in logs
            environment=os.environ.get('ENVIRONMENT', 'production'),
        )
    except ImportError:
        pass

# Production Logging Configuration
LOG_LEVEL = os.environ.get('DJANGO_LOG_LEVEL', 'INFO' if not DEBUG else 'DEBUG')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{name}:{lineno}] {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING' if not DEBUG else 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

