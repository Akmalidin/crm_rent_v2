from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rental', '0011_delivery_cost'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='orders/attachments/', verbose_name='Файл')),
                ('name', models.CharField(max_length=255, verbose_name='Название')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата загрузки')),
                ('order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attachments',
                    to='rental.rentalorder',
                    verbose_name='Заказ',
                )),
                ('uploaded_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='order_attachments',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Загрузил',
                )),
            ],
            options={
                'verbose_name': 'Файл заказа',
                'verbose_name_plural': 'Файлы заказов',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
