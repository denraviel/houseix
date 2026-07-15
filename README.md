# hmoo

`hmoo` is a Django-based hotel and property management system built with a service-layer architecture, Django templates, Bootstrap, and layered authorization.

## Highlights

- Role-based authority using `accounts.CustomUser.role`
- Multi-position operational access using `CustomUser.positions`
- Database-driven feature access using module permissions
- First-login onboarding and self-service account management
- Task, maintenance, sales, inventory, invoicing, expense, room, stay, and reporting modules
- Audit logging for sensitive and operational actions

## Technology Stack

- Python 3.12
- Django 6
- SQLite for development
- PostgreSQL for production
- Bootstrap, `crispy_forms`, `crispy_bootstrap5`
- Gunicorn + WhiteNoise for production runtime

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Copy the environment template:

```bash
cp .env.example .env
```

4. Apply migrations:

```bash
python manage.py migrate
```

5. Create a superuser if needed:

```bash
python manage.py createsuperuser
```

6. Run the development server:

```bash
python manage.py runserver
```

## Settings Layout

- `config/settings/base.py`: shared settings
- `config/settings/development.py`: local development settings
- `config/settings/production.py`: production settings
- `config/settings/__init__.py`: selects the settings module using `DJANGO_ENV`

## Quality Commands

Run formatting and linting locally before pushing:

```bash
black .
isort .
flake8 .
python manage.py check
python manage.py test
```

## Docker

Development:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Production-style local run:

```bash
docker compose up --build
```

## Deployment Docs

- [DEPLOYMENT.md](DEPLOYMENT.md)
- [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
- [docs/Architecture.md](docs/Architecture.md)
- [docs/Authorization.md](docs/Authorization.md)

## Git Workflow

- `main`: production-ready code
- `develop`: integration branch
- `feature/*`: feature work
- `release/*`: release stabilization
- `hotfix/*`: urgent production fixes

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution details.

## Release

Current release candidate target: `v1.0.0-rc1`
