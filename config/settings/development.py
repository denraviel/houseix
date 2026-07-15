# flake8: noqa: F403,F405

from .base import *  # noqa: F403,F401

DEBUG = env_flag('DJANGO_DEBUG', True)
SECRET_KEY = env('DJANGO_SECRET_KEY', 'dev-only-hmoo-secret-key-change-before-production')
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', ['127.0.0.1', 'localhost', 'testserver'])

EMAIL_BACKEND = env('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

SESSION_COOKIE_SECURE = env_flag('DJANGO_SESSION_COOKIE_SECURE', False)
CSRF_COOKIE_SECURE = env_flag('DJANGO_CSRF_COOKIE_SECURE', False)
SECURE_SSL_REDIRECT = env_flag('DJANGO_SECURE_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = env_int('DJANGO_SECURE_HSTS_SECONDS', 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_flag('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_flag('DJANGO_SECURE_HSTS_PRELOAD', False)

STORAGES['staticfiles'] = {  # noqa: F405
    'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
}

LOGGING['loggers']['django']['level'] = 'INFO'  # noqa: F405
LOGGING['loggers']['hmoo']['level'] = 'DEBUG'  # noqa: F405
