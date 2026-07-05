from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .services import AccountOnboardingService, NavigationService


class FirstLoginEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, 'user', None)
        match = getattr(request, 'resolver_match', None)
        url_name = getattr(match, 'url_name', None)

        if not getattr(user, 'is_authenticated', False):
            return None

        if not AccountOnboardingService.requires_onboarding(user):
            return None

        if url_name in AccountOnboardingService.onboarding_exempt_url_names():
            return None

        if request.path.startswith('/admin/'):
            return None

        return redirect('first_login_setup')


class PositionModuleAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path.startswith('/admin/'):
            return None

        user = getattr(request, 'user', None)
        match = getattr(request, 'resolver_match', None)
        url_name = getattr(match, 'url_name', None)

        if getattr(user, 'is_authenticated', False) and url_name:
            if not NavigationService.can_access_url_name(user, url_name):
                return HttpResponseForbidden("You don't have permission to access this operational module.")

        return None
