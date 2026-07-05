from .services import NavigationService


def navigation_context(request):
    user = getattr(request, 'user', None)
    if not getattr(user, 'is_authenticated', False):
        return {
            'navigation_menu': [],
            'accessible_modules': set(),
            'dashboard_title': '',
            'dashboard_widgets': [],
        }
    return {
        'navigation_menu': NavigationService.get_menu_items(user),
        'accessible_modules': NavigationService.get_accessible_modules(user),
        'dashboard_title': NavigationService.get_dashboard_title(user),
        'dashboard_widgets': NavigationService.get_dashboard_widgets(user),
    }
