from django.db import migrations


OPERATIONS_MANAGER_CODE = 'operations_manager'
SUPERVISOR_POSITION_CODES = [
    'hotel_administrator',
    'front_office_supervisor',
    'housekeeping_supervisor',
    'maintenance_supervisor',
    'security_supervisor',
    'chef',
    'store_keeper',
    'procurement_officer',
    'account_officer',
    'marketing_officer',
]

ROLE_PRIORITY = {
    'owner': 4,
    'admin': 3,
    'manager': 2,
    'staff': 1,
}


def _pick_operations_manager(CustomUser, JobPosition, using):
    try:
        ops_position = JobPosition.objects.using(using).get(code=OPERATIONS_MANAGER_CODE, is_active=True)
    except JobPosition.DoesNotExist:
        return None
    qs = CustomUser.objects.using(using).filter(
        positions=ops_position,
        is_active=True,
    ).distinct()
    if not qs.exists():
        return None

    ordered = sorted(
        qs,
        key=lambda u: (-ROLE_PRIORITY.get(u.role, 0), u.date_joined),
    )
    return ordered[0]


def _is_descendant_of(user, supervisor, using):
    visited = set()
    current = user
    for _ in range(50):
        if current is None or current.pk in visited:
            return False
        visited.add(current.pk)
        if current.pk == supervisor.pk:
            return True
        reports_to_id = getattr(current, 'reports_to_id', None)
        if reports_to_id is None:
            return False
        try:
            current = CustomUser.objects.using(using).get(pk=reports_to_id)
        except CustomUser.DoesNotExist:
            return False
    return False


def backfill_ops_manager_hierarchy(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    JobPosition = apps.get_model('accounts', 'JobPosition')
    using = schema_editor.connection.alias

    operations_manager = _pick_operations_manager(CustomUser, JobPosition, using)
    if operations_manager is None:
        return

    supervisor_codes = list(SUPERVISOR_POSITION_CODES)
    qs = CustomUser.objects.using(using).filter(
        positions__code__in=supervisor_codes,
        reports_to__isnull=True,
        is_active=True,
    ).exclude(pk=operations_manager.pk).distinct()

    updated_count = 0
    for user in qs.iterator(chunk_size=100):
        if _is_descendant_of(user, operations_manager, using):
            continue
        if _is_descendant_of(operations_manager, user, using):
            continue
        try:
            user.reports_to = operations_manager
            user.save(using=using, update_fields=['reports_to'])
            updated_count += 1
        except Exception:
            pass
    return updated_count


def noop_backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0014_customuser_reports_to'),
    ]

    operations = [
        migrations.RunPython(backfill_ops_manager_hierarchy, noop_backward),
    ]
