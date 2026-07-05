from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden


def can_manage_maintenance_module(user):
    return getattr(user, 'role', None) in ['owner', 'admin', 'manager', 'staff']


def can_create_maintenance_issue(user):
    return getattr(user, 'role', None) in ['owner', 'admin', 'manager']


def can_view_maintenance_issue(user, issue):
    role = getattr(user, 'role', None)
    if role in ['owner', 'admin', 'manager']:
        return True
    return role == 'staff' and issue.assigned_to_id == getattr(user, 'id', None)


def can_edit_maintenance_issue(user, issue):
    role = getattr(user, 'role', None)
    if role in ['owner', 'admin']:
        return True
    return role == 'manager' and issue.reported_by_id == getattr(user, 'id', None)


def can_assign_maintenance_issue(user):
    return getattr(user, 'role', None) in ['owner', 'admin']


def can_escalate_maintenance_issue(user, issue):
    role = getattr(user, 'role', None)
    if role in ['owner', 'admin']:
        return True
    return role == 'manager' and issue.reported_by_id == getattr(user, 'id', None)


def can_verify_maintenance_issue(user):
    return getattr(user, 'role', None) in ['owner', 'admin', 'manager']


def can_record_maintenance_expense(user):
    return getattr(user, 'role', None) in ['owner', 'admin', 'manager']


class MaintenanceModuleAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not can_manage_maintenance_module(request.user):
            return HttpResponseForbidden("You don't have permission to access maintenance management.")
        return super().dispatch(request, *args, **kwargs)


class MaintenanceAdminAccessMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not can_assign_maintenance_issue(request.user):
            return HttpResponseForbidden("You don't have permission to manage maintenance assignments.")
        return super().dispatch(request, *args, **kwargs)
