from django.core.management.base import BaseCommand
from apps.main.telegram_bot_complete import run_overdue_notifications, run_reminder_notifications

class Command(BaseCommand):
    help = 'Отправить автоматические уведомления'
    
    def handle(self, *args, **options):
        self.stdout.write('📤 Отправка уведомлений...')
        
        # Просрочки
        overdue_count = run_overdue_notifications()
        self.stdout.write(f'⚠️ Просрочки: {overdue_count}')
        
        # Напоминания
        reminder_count = run_reminder_notifications()
        self.stdout.write(f'📅 Напоминания: {reminder_count}')
        
        self.stdout.write(self.style.SUCCESS('✅ Готово!'))