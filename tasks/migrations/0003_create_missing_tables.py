from django.db import migrations


def create_missing_tables(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

    models_to_ensure = [
        ('RoomInspectionChecklist', 'tasks_roominspectionchecklist'),
        ('PerformanceRating', 'tasks_performancerating'),
    ]

    for model_name, table_name in models_to_ensure:
        if table_name in existing_tables:
            continue
        model = apps.get_model('tasks', model_name)
        schema_editor.create_model(model)


class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0002_fix_missing_date_assigned'),
    ]

    operations = [
        migrations.RunPython(create_missing_tables, migrations.RunPython.noop),
    ]

