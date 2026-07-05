from django.http import HttpResponseForbidden

from .services import NavigationService


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
