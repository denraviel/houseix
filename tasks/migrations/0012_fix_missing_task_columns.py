from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0011_remove_task_required_position_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="task",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]