# Deployment

## Supported Targets
- Railway
- Render
- Fly.io
- any container platform that supports Django + Gunicorn

## Runtime Stack
- Gunicorn for application serving
- WhiteNoise for static files
- PostgreSQL for production database
- local or external media storage depending on deployment choice

## Required Steps
1. Configure environment variables.
2. Provision PostgreSQL.
3. Run migrations.
4. Run `collectstatic`.
5. Start Gunicorn.

See the root [DEPLOYMENT.md](../DEPLOYMENT.md) for the full runbook.
