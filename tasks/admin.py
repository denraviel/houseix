from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import (
    InspectionResult,
    InspectionTemplate,
    InspectionTemplateItem,
    MaintenanceActivity,
    MaintenanceCategory,
    MaintenanceIssue,
    MaintenancePhoto,
    PerformanceRating,
    RoomInspectionChecklist,
    Task,
    TaskInspection,
)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'required_position_summary', 'assigned_to', 'priority', 'status', 'requires_inspection', 'due_date', 'is_overdue']
    list_filter = ['status', 'priority', 'task_type', 'requires_inspection', 'required_positions']
    search_fields = ['title', 'description', 'assigned_to__full_name', 'required_positions__name']
    date_hierarchy = 'due_date'
    filter_horizontal = ['required_positions']

    @staticmethod
    def required_position_summary(obj):
        return ', '.join(obj.required_position_names) or '-'


@admin.register(RoomInspectionChecklist)
class RoomInspectionChecklistAdmin(admin.ModelAdmin):
    list_display = ['task', 'inspector', 'get_pass_count', 'inspection_date']


@admin.register(PerformanceRating)
class PerformanceRatingAdmin(admin.ModelAdmin):
    list_display = ['staff', 'rating', 'rated_by', 'date_rated']
    list_filter = ['rating', 'date_rated']


class InspectionTemplateItemInline(admin.TabularInline):
    model = InspectionTemplateItem
    extra = 0


@admin.register(InspectionTemplate)
class InspectionTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'is_active', 'created_at', 'updated_at']
    list_filter = ['role', 'is_active']
    search_fields = ['name', 'description']
    inlines = [InspectionTemplateItemInline]
    filter_horizontal = ['applicable_positions']


class InspectionResultInline(admin.TabularInline):
    model = InspectionResult
    extra = 0
    readonly_fields = ['template_item', 'deduction_applied']


@admin.register(TaskInspection)
class TaskInspectionAdmin(admin.ModelAdmin):
    list_display = ['task', 'template', 'worker', 'inspector', 'result', 'final_score', 'locked', 'submitted_at']
    list_filter = ['result', 'locked', 'template']
    search_fields = ['task__title', 'worker__full_name', 'inspector__full_name']
    inlines = [InspectionResultInline]


class MaintenancePhotoInline(admin.TabularInline):
    model = MaintenancePhoto
    extra = 0


class MaintenanceActivityInline(admin.TabularInline):
    model = MaintenanceActivity
    extra = 0
    readonly_fields = ['activity', 'notes', 'performed_by', 'created_at']
    can_delete = False


@admin.register(MaintenanceCategory)
class MaintenanceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    filter_horizontal = ['assignable_positions']


@admin.register(MaintenanceIssue)
class MaintenanceIssueAdmin(admin.ModelAdmin):
    list_display = ['issue_number', 'title', 'category', 'priority', 'status', 'room', 'assigned_to', 'reported_by', 'created_at']
    list_filter = ['status', 'priority', 'category', 'requires_external_vendor', 'requires_expense']
    search_fields = ['issue_number', 'title', 'description', 'room__room_number', 'reported_by__full_name', 'assigned_to__full_name']
    inlines = [MaintenancePhotoInline, MaintenanceActivityInline]


@admin.register(MaintenancePhoto)
class MaintenancePhotoAdmin(admin.ModelAdmin):
    list_display = ['issue', 'caption', 'uploaded_by', 'uploaded_at']
    search_fields = ['issue__issue_number', 'issue__title', 'caption']


@admin.register(MaintenanceActivity)
class MaintenanceActivityAdmin(admin.ModelAdmin):
    list_display = ['issue', 'activity', 'performed_by', 'created_at']
    list_filter = ['activity', 'created_at']
    search_fields = ['issue__issue_number', 'issue__title', 'notes', 'performed_by__full_name']