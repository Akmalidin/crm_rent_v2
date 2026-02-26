import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Создать бэкап базы данных'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Автоматический режим (без вывода)',
        )
    
    def handle(self, *args, **options):
        auto = options.get('auto', False)
        
        if not auto:
            self.stdout.write('🔄 Создание бэкапа базы данных...')
        
        # Путь к базе данных
        db_path = settings.DATABASES['default']['NAME']
        
        # Папка для бэкапов
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Имя файла с датой и временем
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        backup_filename = f'db_backup_{timestamp}.sqlite3'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        try:
            # Копируем файл БД
            shutil.copy2(db_path, backup_path)
            
            # Размер файла
            size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            
            if not auto:
                self.stdout.write(self.style.SUCCESS(f'✅ Бэкап создан: {backup_filename}'))
                self.stdout.write(f'📁 Размер: {size_mb:.2f} MB')
                self.stdout.write(f'📍 Путь: {backup_path}')
            
            # Удаляем старые бэкапы (оставляем последние 10)
            self.cleanup_old_backups(backup_dir, keep=10)
            
            return backup_path
            
        except Exception as e:
            if not auto:
                self.stdout.write(self.style.ERROR(f'❌ Ошибка: {e}'))
            raise
    
    def cleanup_old_backups(self, backup_dir, keep=10):
        """Удалить старые бэкапы, оставить последние N"""
        
        # Получаем все файлы бэкапов
        backups = []
        for filename in os.listdir(backup_dir):
            if filename.startswith('db_backup_') and filename.endswith('.sqlite3'):
                filepath = os.path.join(backup_dir, filename)
                backups.append((filepath, os.path.getmtime(filepath)))
        
        # Сортируем по времени (новые первые)
        backups.sort(key=lambda x: x[1], reverse=True)
        
        # Удаляем старые
        deleted = 0
        for filepath, _ in backups[keep:]:
            try:
                os.remove(filepath)
                deleted += 1
            except Exception as e:
                self.stdout.write(f'⚠️ Не удалось удалить {filepath}: {e}')
        
        if deleted > 0:
            self.stdout.write(f'🗑️ Удалено старых бэкапов: {deleted}')


# ============================================================
# ИСПОЛЬЗОВАНИЕ
# ============================================================

"""
# Ручной запуск:
python manage.py backup_db

# Автоматический (без вывода):
python manage.py backup_db --auto

# Добавить в crontab для автоматического бэкапа:
# Каждый день в 3:00 ночи
0 3 * * * cd /path/to/project && python manage.py backup_db --auto

# Каждые 6 часов
0 */6 * * * cd /path/to/project && python manage.py backup_db --auto
"""