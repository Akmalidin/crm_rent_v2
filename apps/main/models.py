from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Профиль пользователя.
    owner = None  →  сам является владельцем (директор компании)
    owner = <User>  →  сотрудник, принадлежащий этому директору
    role: 'director' | 'employee'
    """
    ROLE_DIRECTOR = 'director'
    ROLE_EMPLOYEE = 'employee'
    ROLE_CHOICES = [
        ('director', 'Директор'),
        ('employee', 'Сотрудник'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='team_members',
        verbose_name='Директор компании',
    )
    role = models.CharField(
        'Роль', max_length=20,
        choices=ROLE_CHOICES,
        default='director',
    )
    max_warehouses = models.PositiveIntegerField(
        'Макс. складов', default=1,
        help_text='Устанавливается создателем системы',
    )
    needs_company_setup = models.BooleanField(
        'Требует настройки компании', default=False,
    )
    telegram_chat_id = models.CharField(
        'Telegram Chat ID', max_length=50, blank=True, default='',
        help_text='ID из Telegram бота (команда /myid)',
    )

    class Meta:
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f'Профиль: {self.user.username} ({self.get_role_display()})'

    def get_tenant_owner(self):
        """Возвращает владельца тенанта (директора компании)"""
        return self.owner if self.owner_id else self.user

    def is_director(self):
        return self.role == self.ROLE_DIRECTOR

    def is_employee(self):
        return self.role == self.ROLE_EMPLOYEE


class DirectorMessage(models.Model):
    """Тикеты (обращения) от директоров создателю системы"""
    STATUS_OPEN   = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [('open', 'Открыто'), ('closed', 'Закрыто')]

    sender     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', verbose_name='Отправитель')
    subject    = models.CharField('Тема', max_length=200)
    message    = models.TextField('Сообщение')
    status     = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default='open')
    is_read    = models.BooleanField('Прочитано создателем', default=False)
    reply      = models.TextField('Ответ создателя', blank=True, default='')
    replied_at = models.DateTimeField('Дата ответа', null=True, blank=True)
    reply_read = models.BooleanField('Ответ прочитан директором', default=False)
    created_at = models.DateTimeField('Отправлено', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Обращение'
        verbose_name_plural = 'Обращения'
        ordering = ['-created_at']

    def __str__(self):
        return f'#{self.pk} {self.sender.username}: {self.subject}'

    @property
    def ticket_number(self):
        return f'#{self.pk:04d}'

    @property
    def is_open(self):
        return self.status == self.STATUS_OPEN

    @property
    def has_reply(self):
        return bool(self.reply)


class ActivityLog(models.Model):
    """Лог действий сотрудников"""
    ACTION_CHOICES = [
        ('create_order', 'Создал заказ'),
        ('close_order', 'Закрыл заказ'),
        ('edit_order', 'Изменил заказ'),
        ('accept_payment', 'Принял оплату'),
        ('create_client', 'Создал клиента'),
        ('edit_client', 'Изменил клиента'),
        ('create_product', 'Создал товар'),
        ('edit_product', 'Изменил товар'),
        ('return_items', 'Оформил возврат'),
        ('other', 'Другое'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='activity_logs',
        verbose_name='Пользователь',
    )
    action = models.CharField('Действие', max_length=50, choices=ACTION_CHOICES, default='other')
    description = models.TextField('Описание')
    created_at = models.DateTimeField('Время', auto_now_add=True)

    class Meta:
        verbose_name = 'Лог активности'
        verbose_name_plural = 'Лог активности'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} — {self.get_action_display()}'


class RainDay(models.Model):
    """Глобальный дождливый день для компании (владельца)."""
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='rain_days',
        verbose_name='Компания',
    )
    date = models.DateField('Дата дождя')

    class Meta:
        unique_together = [('owner', 'date')]
        verbose_name = 'Дождливый день'
        verbose_name_plural = 'Дождливые дни'
        ordering = ['date']

    def __str__(self):
        return str(self.date)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Автоматически создаёт UserProfile для новых пользователей"""
    if created and not hasattr(instance, '_skip_profile'):
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                'owner': None,
                'role': 'director' if instance.is_superuser else 'employee',
            }
        )
