from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0009_passport_optional'),
        ('inventory', '0007_category_rain_applicable'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientProductDiscount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('discount_per_unit', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Скидка за 1 шт (сом)')),
                ('notes', models.CharField(blank=True, max_length=200, verbose_name='Примечание')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='discounts', to='clients.client', verbose_name='Клиент')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='client_discounts', to='inventory.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Скидка клиента',
                'verbose_name_plural': 'Скидки клиентов',
                'unique_together': {('client', 'product')},
            },
        ),
    ]
