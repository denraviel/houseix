import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sales', '0006_sale_actual_cogs_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='sale',
            name='status',
            field=models.CharField(
                choices=[
                    ('created', 'Order Created'),
                    ('accepted', 'Accepted'),
                    ('preparing', 'Preparing'),
                    ('prepared', 'Prepared / Served'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='created',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='prepared_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sale',
            name='prepared_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='sales_prepared', to=settings.AUTH_USER_MODEL,
                help_text='Staff member who marked this dish as prepared/served, triggering inventory consumption.',
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sale',
            name='cancelled_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='sales_cancelled', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='sale',
            name='cancellation_reason',
            field=models.TextField(blank=True),
        ),
    ]
