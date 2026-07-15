# Authorization

## Three Authorization Layers
- Authority: `owner`, `admin`, `manager`, `staff`
- Job Positions: operational duties such as cleaner, receptionist, barman
- Module Permissions: database-driven feature access to application modules

## Resolution Rules
- Owners retain full access.
- Admins retain broad administrative access and can be configured.
- Managers and staff access modules through explicit module assignments.
- Views must enforce module access on the backend, not only in templates.

## Enforcement Points
- reusable permission mixins
- middleware-based navigation protection
- service-driven navigation and dashboard generation
