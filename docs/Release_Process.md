# Release Process

## Semantic Versioning

- Use `MAJOR.MINOR.PATCH`.
- Pre-release builds use suffixes like `-rc1`, `-rc2`, and `-beta1`.
- Production releases should always be tagged from `main`.

## Branch Roles

- `main`: production branch and release-tag source.
- `develop`: default working branch for ongoing integration.
- `feature/*`: isolated feature or bug-fix branches created from `develop`.
- `release/*`: stabilization branches created from `develop` when preparing a release.
- `hotfix/*`: urgent fixes created from `main`, then merged back into both `main` and `develop`.

## Development Workflow

1. Branch from `develop` using `feature/<name>`.
2. Implement the change, add migrations/tests where needed, and push the feature branch.
3. Open a pull request into `develop`.
4. Merge into `develop` only after review and required checks pass.

## Release Workflow

1. Confirm `develop` contains only work intended for the release.
2. Create `release/<version>` from `develop`.
3. Freeze feature development on the release branch except for stabilization fixes.
4. Run release verification, deployment checks, and documentation review.
5. Merge `release/<version>` into `main`.
6. Tag `main` with the release version.
7. Merge the same release branch back into `develop` if any stabilization-only commits were made.

## Hotfix Workflow

1. Create `hotfix/<name>` from `main`.
2. Apply the urgent production fix and verify it.
3. Merge the hotfix into `main`.
4. Tag a new patch release if needed.
5. Merge the hotfix back into `develop`.

## RC Target

- Current release candidate: `v1.0.0-rc1`

## Required Verification Before Tagging

- `python manage.py check`
- `python manage.py check --deploy`
- `python manage.py test`
- `python manage.py collectstatic --noinput`

## Release Checklist

1. Ensure `main` and the release candidate commit are clean and pushed.
2. Confirm migrations are committed and no local-only files are staged.
3. Verify `.env`, databases, media, and other local artifacts are ignored.
4. Run the required verification commands.
5. Update `CHANGELOG.md` for the release.
6. Create an annotated git tag on `main`.
7. Push `main` and the tag to GitHub.
