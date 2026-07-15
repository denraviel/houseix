# Release Process

## Semantic Versioning
- use `MAJOR.MINOR.PATCH`
- pre-release tags use suffixes like `-rc1`

## Release Branching
1. Merge approved work into `develop`.
2. Create `release/*`.
3. Freeze feature work for stabilization.
4. Run checks, tests, and deployment verification.
5. Merge into `main`.
6. Tag the release.

## RC Target
- current release candidate: `v1.0.0-rc1`

## Required Verification Before Tagging
- `python manage.py check`
- `python manage.py check --deploy`
- `python manage.py test`
- `python manage.py collectstatic --noinput`
