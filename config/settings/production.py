# flake8: noqa: F403,F405

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403,F401

DEBUG = False
SECRET_KEY = env('DJANGO_SECRET_KEY', required=True)
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', [])
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS', [])

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured('DJANGO_ALLOWED_HOSTS must be configured in production.')

if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':  # noqa: F405
    raise ImproperlyConfigured('Production requires PostgreSQL via DATABASE_URL.')

SESSION_COOKIE_SECURE = env_flag('DJANGO_SESSION_COOKIE_SECURE', True)
CSRF_COOKIE_SECURE = env_flag('DJANGO_CSRF_COOKIE_SECURE', True)
SECURE_SSL_REDIRECT = env_flag('DJANGO_SECURE_SSL_REDIRECT', True)
SECURE_HSTS_SECONDS = env_int('DJANGO_SECURE_HSTS_SECONDS', 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_flag('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', True)
SECURE_HSTS_PRELOAD = env_flag('DJANGO_SECURE_HSTS_PRELOAD', True)

STORAGES['staticfiles'] = {  # noqa: F405
    'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
}

LOGGING['loggers']['django']['level'] = env('DJANGO_LOG_LEVEL', 'INFO').upper()  # noqa: F405
LOGGING['loggers']['hmoo']['level'] = env('DJANGO_LOG_LEVEL', 'INFO').upper()  # noqa: F405
