# Coding Standards

## Python
- format with Black
- sort imports with isort
- lint with flake8
- keep functions and classes focused

## Django
- keep views thin
- keep business rules in services, validators, selectors, or mixins
- avoid duplicated permission checks
- use migrations for schema changes

## Templates
- keep templates presentation-only
- use reusable partials where it improves clarity
- avoid embedding business logic in templates
