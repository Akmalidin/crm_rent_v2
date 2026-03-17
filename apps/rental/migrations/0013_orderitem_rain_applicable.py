from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0012_orderattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='rain_applicable',
            field=models.BooleanField(default=False, verbose_name='Дождь не считается'),
        ),
    ]
