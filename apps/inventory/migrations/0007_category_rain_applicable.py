from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_product_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='rain_applicable',
            field=models.BooleanField(
                default=False,
                help_text='Для товаров этой категории можно исключать дождливые дни из аренды',
                verbose_name='Дождь не считается',
            ),
        ),
    ]
