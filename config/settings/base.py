import logging
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[2]


def load_dotenv(env_path):
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv(BASE_DIR / '.env')


def env(name, default=None, required=False):
    value = os.getenv(name, default)
    if value is not None and str(value).strip() == '':
        value = default
    if required and (value is None or str(value).strip() == ''):
        raise ImproperlyConfigured(f'Missing required environment variable: {name}')
    return value


def env_flag(name, default=False):
    value = os.getenv(name)
    if value is None or value.strip() == '':
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_int(name, default=0):
    value = os.getenv(name)
    if value is None or value.strip() == '':
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f'Environment variable {name} must be an integer.') from exc


def env_list(name, default=None):
    value = os.getenv(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(',') if item.strip()]


def database_config(default_sqlite_path):
    database_url = env('DATABASE_URL')
    if not database_url:
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(default_sqlite_path),
        }

    parsed = urlparse(database_url)
    scheme = parsed.scheme.lower()
    if scheme in {'postgres', 'postgresql', 'pgsql'}:
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed.path.lstrip('/')),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or 'localhost',
            'PORT': str(parsed.port or '5432'),
            'CONN_MAX_AGE': env_int('DJANGO_DB_CONN_MAX_AGE', 60),
            'CONN_HEALTH_CHECKS': True,
        }
    if scheme in {'sqlite', 'sqlite3'}:
        sqlite_name = unquote(parsed.path.lstrip('/')) or str(default_sqlite_path)
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': sqlite_name,
        }
    raise ImproperlyConfigured('DATABASE_URL must use postgres/postgresql or sqlite/sqlite3.')


ENVIRONMENT = env('DJANGO_ENV', 'development').strip().lower()
DEBUG = env_flag('DJANGO_DEBUG', False)
SECRET_KEY = env('DJANGO_SECRET_KEY', 'unsafe-development-secret-key')

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', ['127.0.0.1', 'localhost', 'testserver'])
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS', [])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'accounts',
    'tasks',
    'inventory',
    'sales',
    'products',
    'customers',
    'rooms',
    'stays',
    'invoices',
    'expenses',
    'reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.FirstLoginEnforcementMiddleware',
    'accounts.middleware.PositionModuleAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': database_config(BASE_DIR / 'db.sqlite3'),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 10},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'accounts.validators.StrongPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('DJANGO_TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = Path(env('STATIC_ROOT', str(BASE_DIR / 'staticfiles')))
MEDIA_URL = env('MEDIA_URL', '/media/')
MEDIA_ROOT = Path(env('MEDIA_ROOT', str(BASE_DIR / 'media')))

STORAGES = {
    'default': {
        'BACKEND': env('DJANGO_DEFAULT_FILE_STORAGE', 'config.storage.LocalMediaStorage'),
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

AUTH_USER_MODEL = 'accounts.CustomUser'
AUTHENTICATION_BACKENDS = ['accounts.backends.EmailOrUsernameBackend']

CRISPY_TEMPLATE_PACK = 'bootstrap5'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'

EMAIL_BACKEND = env('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', 'localhost')
EMAIL_PORT = env_int('EMAIL_PORT', 25)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_flag('EMAIL_USE_TLS', False)
EMAIL_USE_SSL = env_flag('EMAIL_USE_SSL', False)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'hmoo <noreply@localhost>')
SERVER_EMAIL = env('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env('DJANGO_SESSION_COOKIE_SAMESITE', 'Lax')
SESSION_COOKIE_SECURE = env_flag('DJANGO_SESSION_COOKIE_SECURE', False)
CSRF_COOKIE_SAMESITE = env('DJANGO_CSRF_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SECURE = env_flag('DJANGO_CSRF_COOKIE_SECURE', False)
CSRF_COOKIE_HTTPONLY = env_flag('DJANGO_CSRF_COOKIE_HTTPONLY', False)
SECURE_SSL_REDIRECT = env_flag('DJANGO_SECURE_SSL_REDIRECT', False)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = env_int('DJANGO_SECURE_HSTS_SECONDS', 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_flag('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_flag('DJANGO_SECURE_HSTS_PRELOAD', False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = env('DJANGO_SECURE_REFERRER_POLICY', 'same-origin')
X_FRAME_OPTIONS = env('DJANGO_X_FRAME_OPTIONS', 'DENY')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.navigation_context',
            ],
        },
    },
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

SUPABASE_URL = env('SUPABASE_URL', '')
SUPABASE_ANON_KEY = env('SUPABASE_ANON_KEY', '')
SUPABASE_SERVICE_ROLE_KEY = env('SUPABASE_SERVICE_ROLE_KEY', '')

LOG_LEVEL = env('DJANGO_LOG_LEVEL', 'INFO').upper()
LOG_TO_FILES = env_flag('DJANGO_LOG_TO_FILES', False)
LOG_DIR = Path(env('DJANGO_LOG_DIR', str(BASE_DIR / 'logs')))
if LOG_TO_FILES:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

_audit_handlers = ['audit_file'] if LOG_TO_FILES else ['console']
_security_handlers = ['security_file'] if LOG_TO_FILES else ['console']
_application_handlers = ['application_file'] if LOG_TO_FILES else ['console']

_handlers = {
    'console': {
        'class': 'logging.StreamHandler',
        'formatter': 'structured',
    },
}

if LOG_TO_FILES:
    _handlers.update(
        {
            'audit_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'audit',
                'filename': str(LOG_DIR / 'audit.log'),
                'maxBytes': 1024 * 1024 * 5,
                'backupCount': 5,
            },
            'security_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'security',
                'filename': str(LOG_DIR / 'security.log'),
                'maxBytes': 1024 * 1024 * 5,
                'backupCount': 5,
            },
            'application_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'structured',
                'filename': str(LOG_DIR / 'application.log'),
                'maxBytes': 1024 * 1024 * 5,
                'backupCount': 5,
            },
        }
    )

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'structured': {
            'format': (
                'timestamp={asctime} level={levelname} '
                'logger={name} module={module} message="{message}"'
            ),
            'style': '{',
        },
        'audit': {
            'format': (
                'timestamp={asctime} kind=audit level={levelname} '
                'logger={name} message="{message}"'
            ),
            'style': '{',
        },
        'security': {
            'format': (
                'timestamp={asctime} kind=security level={levelname} '
                'logger={name} message="{message}"'
            ),
            'style': '{',
        },
    },
    'handlers': _handlers,
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'django.security': {
            'handlers': _security_handlers,
            'level': 'WARNING',
            'propagate': False,
        },
        'hmoo': {
            'handlers': _application_handlers,
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'hmoo.audit': {
            'handlers': _audit_handlers,
            'level': 'INFO',
            'propagate': False,
        },
    },
}


logging.captureWarnings(True)
