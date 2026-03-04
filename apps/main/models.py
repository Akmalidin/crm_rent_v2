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
    """Сообщения от директоров создателю системы"""
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='sent_messages',
        verbose_name='Отправитель',
    )
    subject = models.CharField('Тема', max_length=200)
    message = models.TextField('Сообщение')
    created_at = models.DateTimeField('Отправлено', auto_now_add=True)
    is_read = models.BooleanField('Прочитано', default=False)

    class Meta:
        verbose_name = 'Сообщение директора'
        verbose_name_plural = 'Сообщения директоров'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.subject}'


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
