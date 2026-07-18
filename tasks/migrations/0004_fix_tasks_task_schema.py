from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0003_create_missing_tables"),
    ]

    operations = [
        migrations.RunPython(
            migrations.RunPython.noop,
            migrations.RunPython.noop,
        ),
    ]
