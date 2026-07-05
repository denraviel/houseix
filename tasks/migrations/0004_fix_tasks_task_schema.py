from django.db import migrations


def fix_tasks_task_schema(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info('tasks_task')")
        existing_columns = {row[1] for row in cursor.fetchall()}

        columns_to_add = []

        if 'task_type' not in existing_columns:
            columns_to_add.append(("task_type", "varchar(50)", "'other'", False))
        if 'priority' not in existing_columns:
            columns_to_add.append(("priority", "varchar(10)", "'medium'", False))
        if 'completion_notes' not in existing_columns:
            columns_to_add.append(("completion_notes", "TEXT", "''", False))
        if 'completed_at' not in existing_columns:
            columns_to_add.append(("completed_at", "datetime", None, True))

        for name, sql_type, default_sql, nullable in columns_to_add:
            if nullable:
                cursor.execute(f"ALTER TABLE tasks_task ADD COLUMN {name} {sql_type}")
            else:
                cursor.execute(f"ALTER TABLE tasks_task ADD COLUMN {name} {sql_type} NOT NULL DEFAULT {default_sql}")

        if 'task_type' in {c[0] for c in columns_to_add}:
            cursor.execute("UPDATE tasks_task SET task_type = 'other' WHERE task_type IS NULL OR task_type = ''")
        if 'priority' in {c[0] for c in columns_to_add}:
            cursor.execute("UPDATE tasks_task SET priority = 'medium' WHERE priority IS NULL OR priority = ''")
        if 'completion_notes' in {c[0] for c in columns_to_add}:
            cursor.execute("UPDATE tasks_task SET completion_notes = '' WHERE completion_notes IS NULL")


class Migration(migrations.Migration):
    dependencies = [
        ('tasks', '0003_create_missing_tables'),
    ]

    operations = [
        migrations.RunPython(fix_tasks_task_schema, migrations.RunPython.noop),
    ]

