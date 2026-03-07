"""
Django management command: python manage.py run_bot
Запускает Telegram бота в режиме long polling.
Работает как systemd сервис на сервере.
"""
import time
import requests
import json
import logging

from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запустить Telegram бота (long polling)'

    def handle(self, *args, **options):
        from apps.main.tg_handlers import handle_command, handle_callback_query

        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not token:
            self.stderr.write('TELEGRAM_BOT_TOKEN не задан!')
            return

        base_url = f'https://api.telegram.org/bot{token}'
        offset = None

        self.stdout.write(self.style.SUCCESS('Telegram бот запущен (polling)...'))

        while True:
            try:
                params = {'timeout': 30, 'allowed_updates': ['message', 'callback_query']}
                if offset is not None:
                    params['offset'] = offset

                resp = requests.get(f'{base_url}/getUpdates', params=params, timeout=35)
                data = resp.json()

                if not data.get('ok'):
                    self.stderr.write(f'getUpdates error: {data}')
                    time.sleep(5)
                    continue

                for update in data.get('result', []):
                    offset = update['update_id'] + 1
                    try:
                        if 'message' in update:
                            handle_command(update['message'])
                        elif 'callback_query' in update:
                            handle_callback_query(update['callback_query'])
                    except Exception as e:
                        logger.exception(f'Error processing update {update["update_id"]}: {e}')

            except requests.exceptions.Timeout:
                # Normal — long poll timeout
                continue
            except Exception as e:
                logger.exception(f'Polling error: {e}')
                time.sleep(5)
