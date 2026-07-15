# Production Checklist

## Environment
- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY` configured
- `DJANGO_ALLOWED_HOSTS` configured
- `DJANGO_CSRF_TRUSTED_ORIGINS` configured
- `DATABASE_URL` points to PostgreSQL
- email settings configured
- security settings reviewed

## Database
- PostgreSQL is reachable
- `python manage.py migrate --noinput` completed
- module permissions seeded
- job positions seeded
- default data verified

## Static and Media
- `python manage.py collectstatic --noinput` completed
- `STATIC_ROOT` configured
- `MEDIA_ROOT` or external media storage configured

## Accounts and Access
- superuser created
- owner account created and verified
- admin accounts verified
- onboarding flow verified
- module permission assignments verified

## Operations
- backups configured
- log retention configured
- monitoring configured
- error alerting configured
- rollback plan documented

## Application Validation
- `python manage.py check` passes
- `python manage.py check --deploy` passes
- `python manage.py test` passes
- core workflows smoke tested
- no broken templates or URLs detected
