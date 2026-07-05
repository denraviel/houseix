from django.http import HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin

from .services import NavigationService


class OperationalModuleAccessMixin(LoginRequiredMixin):
    module_code = ''

    def dispatch(self, request, *args, **kwargs):
        if self.module_code and not NavigationService.can_access_module(request.user, self.module_code):
            return HttpResponseForbidden("You don't have permission to access this operational module.")
        return super().dispatch(request, *args, **kwargs)
