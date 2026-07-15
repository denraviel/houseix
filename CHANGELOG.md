# Changelog

All notable changes to this project will be documented in this file.

The format follows Keep a Changelog principles and semantic versioning for releases.

## [v1.0.0-rc1] - 2026-07-08

### Added
- Environment-driven settings package for development and production
- PostgreSQL-ready database configuration for production
- WhiteNoise-based static file serving
- Gunicorn runtime configuration and Procfile
- Docker and Docker Compose setup
- GitHub Actions CI workflow
- Repository standards files: `.editorconfig`, `.pre-commit-config.yaml`, `.env.example`
- RC deployment and operational documentation

### Changed
- Simplified runtime dependency list to required application and production packages
- Centralized logging, storage, and security settings
- Improved repository hygiene for GitHub and deployment readiness

### Removed
- Legacy single-file settings module
- Unsafe helper scripts containing local development shortcuts
