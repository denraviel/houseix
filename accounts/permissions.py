from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden

from .services import ModulePermissionService, NavigationService


class ModuleAccessMixin(LoginRequiredMixin):
    module_code = ''
    permission_denied_message = "You don't have permission to access this module."

    def dispatch(self, request, *args, **kwargs):
        if self.module_code and not ModulePermissionService.can_access_module(request.user, self.module_code):
            return HttpResponseForbidden(self.permission_denied_message)
        return super().dispatch(request, *args, **kwargs)


class ModulePermissionRequiredMixin(ModuleAccessMixin):
    pass


class OperationalModuleAccessMixin(ModulePermissionRequiredMixin):
    permission_denied_message = "You don't have permission to access this operational module."


class OwnerRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'owner':
            return HttpResponseForbidden("Only the owner can perform this action.")
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) not in ['owner', 'admin']:
            return HttpResponseForbidden("Only owner or admin users can perform this action.")
        return super().dispatch(request, *args, **kwargs)


class ManagerRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'manager':
            return HttpResponseForbidden("Only manager users can perform this action.")
        return super().dispatch(request, *args, **kwargs)


class StaffRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'staff':
            return HttpResponseForbidden("Only staff users can perform this action.")
        return super().dispatch(request, *args, **kwargs)


def module_permission_required(module_code):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not getattr(request.user, 'is_authenticated', False):
                return HttpResponseForbidden("Authentication is required.")
            if not ModulePermissionService.can_access_module(request.user, module_code):
                return HttpResponseForbidden("You don't have permission to access this module.")
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def has_module_access(user, module_code):
    return ModulePermissionService.can_access_module(user, module_code)
