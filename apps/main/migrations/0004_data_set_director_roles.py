from django.db import migrations


def set_director_roles(apps, schema_editor):
    UserProfile = apps.get_model('main', 'UserProfile')
    # All profiles with owner=None are directors
    UserProfile.objects.filter(owner__isnull=True).update(role='director')
    # All profiles with owner set are employees
    UserProfile.objects.filter(owner__isnull=False).update(role='employee')


class Migration(migrations.Migration):
    dependencies = [
        ('main', '0003_userprofile_role_max_warehouses_directormessage'),
    ]

    operations = [
        migrations.RunPython(set_director_roles, migrations.RunPython.noop),
    ]
