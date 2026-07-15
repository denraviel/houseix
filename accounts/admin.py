from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import ActivityLog, AuditLog, CustomUser, JobPosition, ModulePermission


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        'email',
        'username',
        'full_name',
        'phone_number',
        'role',
        'position_summary',
        'is_first_login',
        'is_staff',
        'is_superuser',
    )
    list_filter = (
        'role',
        'is_first_login',
        'email_verified',
        'module_permissions_configured',
        'positions__department',
        'positions',
        'module_permissions',
        'is_staff',
        'is_superuser',
    )
    search_fields = (
        'email',
        'username',
        'full_name',
        'phone_number',
        'positions__name',
        'positions__code',
        'module_permissions__name',
        'module_permissions__code',
    )
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'display_name', 'phone_number', 'profile_photo', 'positions')}),
        ('Module Access', {'fields': ('module_permissions_configured', 'module_permissions')}),
        ('Account Security', {'fields': ('is_first_login', 'email_verified', 'password_changed_at')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'full_name', 'display_name', 'phone_number', 'role', 'positions', 'module_permissions', 'password1', 'password2'),
        }),
    )

    filter_horizontal = ('positions', 'module_permissions', 'groups', 'user_permissions')

    @staticmethod
    def position_summary(obj):
        return ', '.join(obj.position_names) or '-'


@admin.register(JobPosition)
class JobPositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department', 'is_active', 'created_at', 'updated_at')
    list_filter = ('department', 'is_active')
    search_fields = ('name', 'code', 'description')


@admin.register(ModulePermission)
class ModulePermissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'module_url_name', 'display_order', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description', 'module_url_name')

    def save_model(self, request, obj, form, change):
        previous_is_active = None
        if change:
            previous_is_active = ModulePermission.objects.filter(pk=obj.pk).values_list('is_active', flat=True).first()
        super().save_model(request, obj, form, change)
        if not change:
            AuditLog.log(request.user, 'module_permission_created', f'Created module permission {obj.code}.')
        elif previous_is_active and not obj.is_active:
            AuditLog.log(request.user, 'module_permission_disabled', f'Disabled module permission {obj.code}.')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action_type', 'actor', 'description')
    list_filter = ('action_type', 'created_at')
    search_fields = ('description', 'actor__email', 'actor__full_name')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'action_type', 'user_full_name', 'user_role', 'customer', 'booking')
    list_filter = ('action_type', 'timestamp', 'user_role')
    search_fields = ('notes', 'user_full_name', 'user_username', 'customer__full_name')
