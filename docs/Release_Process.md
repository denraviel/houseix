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
1. Create `hotfix/<name>` from `main`.
2. Apply the urgent production fix and verify it.
- current release candidate: `v1.0.0-rc1`
4. Tag a new patch release if needed.
5. Merge the hotfix back into `develop`.

## RC Target

- Current release candidate: `v1.0.0-rc1`

1. Ensure `main` and the release candidate commit are clean and pushed.
2. Confirm migrations are committed and no local-only files are staged.
3. Verify `.env`, databases, media, and other local artifacts are ignored.
4. Run the required verification commands.
5. Update `CHANGELOG.md` for the release.
6. Create an annotated git tag on `main`.
7. Push `main` and the tag to GitHub.
