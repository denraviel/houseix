# Troubleshooting

## Common Issues
- `DisallowedHost`: update `DJANGO_ALLOWED_HOSTS`
- static files missing: run `collectstatic` and verify `STATIC_ROOT`
- media uploads not resolving: verify `MEDIA_ROOT` or external storage config
- database connection errors: verify `DATABASE_URL`
- HTTPS redirect loops: verify proxy headers and platform TLS setup
- migration mismatch: run `python manage.py makemigrations --check` and `python manage.py showmigrations`

## Debugging Tips
- run `python manage.py check`
- run `python manage.py check --deploy`
- inspect logs from the `django`, `hmoo`, and `hmoo.audit` loggers
