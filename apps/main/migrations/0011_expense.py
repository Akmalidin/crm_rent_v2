from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0010_ticketreply'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    choices=[
                        ('rent', 'Аренда помещения'), ('salary', 'Зарплата'),
                        ('transport', 'Транспорт'), ('repair', 'Ремонт техники'),
                        ('utilities', 'Коммунальные услуги'), ('marketing', 'Реклама'),
                        ('purchase', 'Закупка оборудования'), ('other', 'Прочее'),
                    ],
                    default='other', max_length=20, verbose_name='Категория'
                )),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Сумма')),
                ('description', models.CharField(blank=True, max_length=300, verbose_name='Описание')),
                ('date', models.DateField(verbose_name='Дата')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Добавлено')),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='expenses',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Компания',
                )),
            ],
            options={
                'verbose_name': 'Расход',
                'verbose_name_plural': 'Расходы',
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]
