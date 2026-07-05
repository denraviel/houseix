from django.db import migrations


def mark_existing_users_as_onboarded(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    CustomUser.objects.all().update(is_first_login=False)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0009_customuser_display_name_customuser_email_verified_and_more'),
    ]

    operations = [
        migrations.RunPython(mark_existing_users_as_onboarded, migrations.RunPython.noop),
    ]
