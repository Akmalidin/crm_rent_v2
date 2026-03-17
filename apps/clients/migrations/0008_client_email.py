from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0007_assign_existing_clients_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='email',
            field=models.EmailField(blank=True, null=True, verbose_name='Email'),
        ),
    ]
