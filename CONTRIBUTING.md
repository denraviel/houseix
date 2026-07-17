# Contributing to hmoo

## Branch Strategy

- `main`: deployable production branch
- `develop`: integration branch for approved work
- `feature/*`: isolated feature development
- `release/*`: release candidate stabilization
- `hotfix/*`: urgent fixes against production

## Local Setup

1. Create a virtual environment.
2. Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Copy `.env.example` to `.env`.
4. Run `python manage.py migrate`.
5. Run `python manage.py test`.

## Coding Standards

- Preserve the existing service-layer architecture.
- Keep Django class-based views thin.
- Put business logic in services, selectors, validators, and mixins where appropriate.
- Keep templates presentation-only.
- Maintain backward compatibility.
- Do not redesign authorization layers without an approved architecture change.

## Required Checks Before Opening a PR

```bash
black .
isort .
flake8 .
python manage.py check
python manage.py test
```

## Commit Guidelines

- Use small, focused commits.
- Keep migrations with the code that requires them.
- Write commit messages in imperative mood.

## Pull Request Expectations

- Explain the problem and the solution.
- Mention schema changes, migrations, and verification steps.
- Include screenshots for UI changes when relevant.
- Note any follow-up work explicitly.

5. Tag the release using semantic versioning.
6. Merge any release-only fixes back into `develop`.

## Default Branch Usage

- Use `develop` as the default working branch for day-to-day development.
- Keep `main` reserved for production-ready code only.
- Start all new feature branches from `develop` unless you are making a production hotfix.
