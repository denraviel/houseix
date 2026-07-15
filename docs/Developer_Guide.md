# Developer Guide

## Setup
1. Install Python 3.12.
2. Create a virtual environment.
3. Install `requirements-dev.txt`.
4. Copy `.env.example` to `.env`.
5. Run migrations and tests.

## Daily Commands

```bash
python manage.py runserver
python manage.py test
python manage.py check
black .
isort .
flake8 .
```

## Expectations
- do not commit secrets
- do not commit local databases or media
- preserve backward compatibility
- add tests for meaningful regressions
