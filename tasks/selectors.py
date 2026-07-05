from datetime import timedelta

from django.db.models import Avg, Count, F, Q, Sum
from django.utils import timezone

from .models import MaintenanceActivity, MaintenanceIssue, MaintenancePhoto


def accessible_maintenance_issues_queryset(user):
    queryset = MaintenanceIssue.objects.select_related(
        'category',
        'room',
        'reported_by',
        'assigned_to',
        'verified_by',
        'task',
        'expense',
    )
    role = getattr(user, 'role', None)
    if role in ['owner', 'admin', 'manager']:
        return queryset
    if role == 'staff':
        return queryset.filter(assigned_to=user)
    return queryset.none()


def accessible_maintenance_activities_queryset(user):
    issue_queryset = accessible_maintenance_issues_queryset(user).values_list('pk', flat=True)
    return MaintenanceActivity.objects.select_related('issue', 'performed_by').filter(issue_id__in=issue_queryset)


def accessible_maintenance_photos_queryset(user):
    issue_queryset = accessible_maintenance_issues_queryset(user).values_list('pk', flat=True)
    return MaintenancePhoto.objects.select_related('issue', 'uploaded_by').filter(issue_id__in=issue_queryset)


def maintenance_dashboard_snapshot(user):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    issues = accessible_maintenance_issues_queryset(user)
    open_statuses = [
        MaintenanceIssue.STATUS_REPORTED,
        MaintenanceIssue.STATUS_ACKNOWLEDGED,
        MaintenanceIssue.STATUS_ASSIGNED,
        MaintenanceIssue.STATUS_IN_PROGRESS,
        MaintenanceIssue.STATUS_WAITING_PARTS,
        MaintenanceIssue.STATUS_WAITING_VENDOR,
        MaintenanceIssue.STATUS_REOPENED,
        MaintenanceIssue.STATUS_COMPLETED,
    ]
    open_issues = issues.filter(status__in=open_statuses)
    recent_activities = accessible_maintenance_activities_queryset(user).order_by('-created_at')[:10]
    recent_photos = accessible_maintenance_photos_queryset(user).order_by('-uploaded_at')[:12]
    room_with_most_issues = (
        issues.exclude(room__isnull=True)
        .values('room', 'room__room_number')
        .annotate(total_issues=Count('id'))
        .order_by('-total_issues', 'room__room_number')
        .first()
    )
    top_categories = (
        issues.values('category__name')
        .annotate(total_issues=Count('id'))
        .order_by('-total_issues', 'category__name')[:5]
    )
    return {
        'open_issues_count': open_issues.exclude(status=MaintenanceIssue.STATUS_COMPLETED).count(),
        'emergency_issues_count': open_issues.filter(priority=MaintenanceIssue.PRIORITY_EMERGENCY).count(),
        'high_priority_count': open_issues.filter(priority=MaintenanceIssue.PRIORITY_HIGH).count(),
        'waiting_assignment_count': issues.filter(
            Q(assigned_to__isnull=True) | Q(status__in=[MaintenanceIssue.STATUS_REPORTED, MaintenanceIssue.STATUS_ACKNOWLEDGED])
        ).exclude(status=MaintenanceIssue.STATUS_VERIFIED).count(),
        'waiting_vendor_count': issues.filter(status=MaintenanceIssue.STATUS_WAITING_VENDOR).count(),
        'in_progress_count': issues.filter(status=MaintenanceIssue.STATUS_IN_PROGRESS).count(),
        'completed_today_count': issues.filter(resolved_at__date=today).count(),
        'pending_verification_count': issues.filter(status=MaintenanceIssue.STATUS_COMPLETED).count(),
        'recently_reported': issues.order_by('-created_at')[:10],
        'recent_activities': recent_activities,
        'recent_photos': recent_photos,
        'room_with_most_issues': room_with_most_issues,
        'top_categories': top_categories,
        'month_start': month_start,
        'month_issues_count': issues.filter(created_at__date__gte=month_start).count(),
    }


def maintenance_report_queryset():
    return MaintenanceIssue.objects.select_related('category', 'room', 'assigned_to', 'reported_by', 'expense', 'task')


def maintenance_issue_summary_by_category(queryset=None):
    queryset = queryset or maintenance_report_queryset()
    return queryset.values('category__name').annotate(total_issues=Count('id')).order_by('-total_issues', 'category__name')


def maintenance_issue_summary_by_priority(queryset=None):
    queryset = queryset or maintenance_report_queryset()
    return queryset.values('priority').annotate(total_issues=Count('id')).order_by('priority')


def maintenance_cost_by_category(queryset=None):
    queryset = queryset or maintenance_report_queryset()
    return queryset.exclude(expense__isnull=True).values('category__name').annotate(total_cost=Sum('expense__amount')).order_by('-total_cost')


def maintenance_cost_by_room(queryset=None):
    queryset = queryset or maintenance_report_queryset()
    return queryset.filter(room__isnull=False, expense__isnull=False).values('room__room_number').annotate(total_cost=Sum('expense__amount')).order_by('-total_cost')


def maintenance_cost_by_vendor(queryset=None):
    queryset = queryset or maintenance_report_queryset()
    return queryset.exclude(expense__vendor__isnull=True).values('expense__vendor__name').annotate(total_cost=Sum('expense__amount')).order_by('-total_cost')


def average_resolution_time(queryset=None):
    queryset = queryset or maintenance_report_queryset()
    resolved_queryset = queryset.filter(resolved_at__isnull=False)
    if not resolved_queryset.exists():
        return timedelta(0)
    total = timedelta(0)
    for issue in resolved_queryset:
        total += issue.resolved_at - issue.created_at
    return total / resolved_queryset.count()
