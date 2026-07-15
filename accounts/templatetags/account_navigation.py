from django import template

from accounts.services import ModulePermissionService

register = template.Library()


@register.simple_tag
def has_module_access(user, module_code):
    return ModulePermissionService.can_access_module(user, module_code)


@register.simple_tag
def get_accessible_modules(user):
    return ModulePermissionService.get_accessible_module_codes(user)
