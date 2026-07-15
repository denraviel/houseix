# Deployment Guide

## Local Setup
1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Copy `.env.example` to `.env`.
4. Set `DJANGO_ENV=development`.
5. Run:

```bash
python manage.py migrate
python manage.py runserver
```

## Required Environment Variables
- `DJANGO_ENV`
- `DJANGO_DEBUG`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`
- `STATIC_ROOT`
- `MEDIA_ROOT`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`
- `SUPABASE_URL` for future storage integration
- `SUPABASE_ANON_KEY` for future storage integration
- `SUPABASE_SERVICE_ROLE_KEY` for future storage integration

See `.env.example` and [docs/Environment_Variables.md](docs/Environment_Variables.md).

## GitHub Push Workflow
1. Branch from `develop` or `main` using `feature/*`, `release/*`, or `hotfix/*`.
2. Run formatting, checks, and tests locally.
3. Push the branch to GitHub.
4. Open a pull request.
5. Wait for GitHub Actions CI to pass before merging.

## Railway Deployment
1. Create a Railway project and connect the GitHub repository.
2. Add all production environment variables.
3. Provision PostgreSQL or connect to Supabase PostgreSQL.
4. Ensure the start command uses the `Procfile` or `gunicorn config.wsgi:application --config gunicorn.conf.py`.
5. Run migrations during release using the `release` process.

## Render Deployment
1. Create a new Web Service from the GitHub repository.
2. Set the build command:

```bash
pip install -r requirements.txt && python manage.py collectstatic --noinput
```

3. Set the start command:

```bash
gunicorn config.wsgi:application --config gunicorn.conf.py
```

4. Add a PostgreSQL database and all required environment variables.

## Supabase PostgreSQL Configuration
1. Create a Supabase project.
2. Copy the connection string.
3. Set `DATABASE_URL` with the PostgreSQL connection string.
4. Keep Supabase Storage settings empty until media storage is implemented later.

## Database Migration
Run on each deployment:

```bash
python manage.py migrate --noinput
```

## Static File Collection
Run on each deployment:

```bash
python manage.py collectstatic --noinput
```

## Superuser Creation
After first deployment:

```bash
python manage.py createsuperuser
```

## Rollback Procedure
1. Roll back application code to the previous Git tag or release.
2. If the release included migrations, assess whether the schema is backward compatible before downgrading.
3. Restore the previous database backup if necessary.
4. Re-run `collectstatic`.
5. Verify login, dashboards, and critical workflows.

## Common Deployment Issues
- Missing `DJANGO_SECRET_KEY`
- Incorrect `DJANGO_ALLOWED_HOSTS`
- Wrong `DATABASE_URL`
- Static files not collected
- Missing PostgreSQL driver
- HTTPS proxy headers not configured on the platform

## Verification Checklist
- `python manage.py check`
- `python manage.py check --deploy`
- `python manage.py test`
- Admin login works
- Owner account works
- Static assets load
- Media uploads work in the chosen environment
