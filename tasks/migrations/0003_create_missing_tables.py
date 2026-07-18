from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0002_fix_missing_date_assigned"),
    ]

    operations = [
        migrations.RunPython(
            migrations.RunPython.noop,
            migrations.RunPython.noop,
        ),
    ]