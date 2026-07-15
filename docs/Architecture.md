# Architecture

## Overview
`hmoo` uses a layered Django architecture built around:
- thin class-based views
- service classes for business logic
- form validation for request data
- selectors and validators where domain logic benefits from separation
- Django templates for server-rendered UI

## Key Layers
- `role`: authority layer on `accounts.CustomUser.role`
- `positions`: operational responsibility layer on `CustomUser.positions`
- `module_permissions`: feature access layer on `CustomUser.module_permissions`

## Design Goals
- preserve backward compatibility
- keep app boundaries clear
- avoid duplicating business logic
- keep templates presentation-only
- support future cloud deployment without refactoring domain logic
