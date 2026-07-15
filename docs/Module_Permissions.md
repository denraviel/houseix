# Module Permissions

## Purpose
Module permissions provide the third authorization layer and control which application modules a user may access.

## Characteristics
- database-driven
- assignable per user
- independent of authority role and job positions
- used for navigation and backend authorization

## Defaults
- dashboard and account access remain available
- everything else should be granted explicitly unless the user is an owner

## Implementation
- `ModulePermission` model
- `ModulePermissionService`
- permission mixins and template tags
