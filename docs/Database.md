# Database

## Development
- SQLite is used for local development.
- `DATABASE_URL` may be omitted to fall back to `db.sqlite3`.

## Production
- PostgreSQL is required in `config/settings/production.py`.
- `DATABASE_URL` must be set to a PostgreSQL connection string.

## Migration Policy
- commit migrations with the related code changes
- validate with `python manage.py makemigrations --check`
- apply with `python manage.py migrate --noinput`
