from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0013_backfill_module_permissions_from_legacy_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='reports_to',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='direct_reports',
                to='accounts.customuser',
            ),
        ),
    ]