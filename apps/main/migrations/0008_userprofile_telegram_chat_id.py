from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0007_rainday'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='telegram_chat_id',
            field=models.CharField('Telegram Chat ID', max_length=50, blank=True, default='',
                                   help_text='ID из Telegram бота (команда /myid)'),
        ),
    ]
