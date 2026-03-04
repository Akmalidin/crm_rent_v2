from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0008_orderexcludedday_order_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='returnitem',
            name='repair_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Плата за ремонт/чистку'),
        ),
        migrations.AddField(
            model_name='returnitem',
            name='repair_notes',
            field=models.TextField(blank=True, verbose_name='Примечание по ремонту'),
        ),
    ]
