from django.db import migrations, models
import django.db.models.deletion


def clear_old_excluded_days(apps, schema_editor):
    """Очищаем старые записи — они без order_item, не совместимы с новой схемой"""
    OrderExcludedDay = apps.get_model('rental', 'OrderExcludedDay')
    OrderExcludedDay.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0007_order_excluded_day'),
    ]

    operations = [
        # 1. Удаляем старые данные (они без order_item)
        migrations.RunPython(clear_old_excluded_days, migrations.RunPython.noop),

        # 2. Убираем старое unique_together
        migrations.AlterUniqueTogether(
            name='orderexcludedday',
            unique_together=set(),
        ),

        # 3. Добавляем order_item FK (nullable)
        migrations.AddField(
            model_name='orderexcludedday',
            name='order_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='excluded_days',
                to='rental.orderitem',
                verbose_name='Позиция заказа',
            ),
        ),

        # 4. Новое unique_together по (order_item, date)
        migrations.AlterUniqueTogether(
            name='orderexcludedday',
            unique_together={('order_item', 'date')},
        ),
    ]
