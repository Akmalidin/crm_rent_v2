from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0006_userprofile_needs_company_setup'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RainDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Дата дождя')),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rain_days',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Компания',
                )),
            ],
            options={
                'verbose_name': 'Дождливый день',
                'verbose_name_plural': 'Дождливые дни',
                'ordering': ['date'],
                'unique_together': {('owner', 'date')},
            },
        ),
    ]
