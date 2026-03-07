from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_userprofile_telegram_chat_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='directormessage',
            name='status',
            field=models.CharField(choices=[('open', 'Открыто'), ('closed', 'Закрыто')], default='open', max_length=10, verbose_name='Статус'),
        ),
        migrations.AddField(
            model_name='directormessage',
            name='reply',
            field=models.TextField(blank=True, default='', verbose_name='Ответ создателя'),
        ),
        migrations.AddField(
            model_name='directormessage',
            name='replied_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Дата ответа'),
        ),
        migrations.AddField(
            model_name='directormessage',
            name='reply_read',
            field=models.BooleanField(default=False, verbose_name='Ответ прочитан директором'),
        ),
        migrations.AddField(
            model_name='directormessage',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Обновлено'),
        ),
    ]
