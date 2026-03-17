import uuid
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
    phone = models.CharField(
        'Телефон', max_length=30, blank=True, default='',
        help_text='Номер телефона для связи',
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

    @property
    def unread_for_sender(self):
        """Есть непрочитанные ответы от создателя для отправителя."""
        return self.replies.filter(is_read=False).exclude(author=self.sender).exists()

    @property
    def unread_for_creator(self):
        """Есть непрочитанные сообщения от отправителя для создателя."""
        return self.replies.filter(is_read=False, author=self.sender).exists()


class TicketReply(models.Model):
    """Сообщения внутри тикета (чат между директором и создателем)"""
    ticket     = models.ForeignKey(DirectorMessage, on_delete=models.CASCADE, related_name='replies', verbose_name='Тикет')
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ticket_replies', verbose_name='Автор')
    text       = models.TextField('Сообщение')
    is_read    = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField('Дата', auto_now_add=True)

    class Meta:
        verbose_name = 'Ответ в тикете'
        verbose_name_plural = 'Ответы в тикетах'
        ordering = ['created_at']

    def __str__(self):
        return f'Тикет #{self.ticket_id} — {self.author.username}'


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


class RequestLog(models.Model):
    """Лог HTTP-запросов (каждое обращение к серверу)"""
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='request_logs', verbose_name='Пользователь'
    )
    username = models.CharField('Логин', max_length=150, blank=True)
    ip = models.GenericIPAddressField('IP-адрес', null=True, blank=True)
    method = models.CharField('Метод', max_length=10)
    path = models.CharField('URL', max_length=500)
    query = models.CharField('Параметры', max_length=500, blank=True)
    status_code = models.PositiveSmallIntegerField('Статус')
    response_ms = models.PositiveIntegerField('Время ответа (мс)', default=0)
    user_agent = models.CharField('User-Agent', max_length=500, blank=True)
    referer = models.CharField('Referer', max_length=500, blank=True)
    event = models.CharField('Событие', max_length=50, blank=True)  # login/logout/page_close
    created_at = models.DateTimeField('Время', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Запрос'
        verbose_name_plural = 'Лог запросов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.username} {self.method} {self.path} {self.status_code}'


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


class Expense(models.Model):
    """Расходы компании (директора)"""
    CATEGORY_CHOICES = [
        ('rent',        'Аренда помещения'),
        ('salary',      'Зарплата'),
        ('transport',   'Транспорт'),
        ('repair',      'Ремонт техники'),
        ('utilities',   'Коммунальные услуги'),
        ('marketing',   'Реклама'),
        ('purchase',    'Закупка оборудования'),
        ('other',       'Прочее'),
    ]

    owner       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses', verbose_name='Компания')
    category    = models.CharField('Категория', max_length=20, choices=CATEGORY_CHOICES, default='other')
    amount      = models.DecimalField('Сумма', max_digits=12, decimal_places=2)
    description = models.CharField('Описание', max_length=300, blank=True)
    date        = models.DateField('Дата')
    created_at  = models.DateTimeField('Добавлено', auto_now_add=True)

    class Meta:
        verbose_name = 'Расход'
        verbose_name_plural = 'Расходы'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.get_category_display()} — {self.amount} — {self.date}'


class ClientPortalToken(models.Model):
    """Токен для доступа клиента к порталу бронирования."""
    client = models.OneToOneField(
        'clients.Client', on_delete=models.CASCADE,
        related_name='portal_token', verbose_name='Клиент',
    )
    token = models.UUIDField('Токен', default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Токен клиентского портала'
        verbose_name_plural = 'Токены клиентского портала'

    def __str__(self):
        return f'Токен: {self.client} ({self.token})'


class Notification(models.Model):
    """Push-уведомления для пользователей (SSE)"""
    TYPE_ORDER   = 'order'
    TYPE_PAYMENT = 'payment'
    TYPE_BOOKING = 'booking'
    TYPE_TICKET  = 'ticket'
    TYPE_OVERDUE = 'overdue'
    TYPE_INFO    = 'info'
    TYPE_CHOICES = [
        ('order',   'Новый заказ'),
        ('payment', 'Оплата'),
        ('booking', 'Заявка'),
        ('ticket',  'Сообщение'),
        ('overdue', 'Просрочка'),
        ('info',    'Информация'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name='Получатель')
    type       = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES, default='info')
    title      = models.CharField('Заголовок', max_length=200)
    message    = models.CharField('Текст', max_length=500, blank=True)
    link       = models.CharField('Ссылка', max_length=300, blank=True)
    is_read    = models.BooleanField('Прочитано', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.title}'


class BookingRequest(models.Model):
    """Заявка на бронирование от клиента через портал."""
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
    ]

    client = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE,
        related_name='booking_requests', verbose_name='Клиент',
    )
    product = models.ForeignKey(
        'inventory.Product', on_delete=models.CASCADE,
        related_name='booking_requests', verbose_name='Товар',
    )
    quantity = models.PositiveIntegerField('Количество', default=1)
    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата окончания')
    comment = models.TextField('Комментарий клиента', blank=True)
    status = models.CharField('Статус', max_length=10, choices=STATUS_CHOICES, default='pending')
    admin_comment = models.TextField('Комментарий администратора', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Заявка на бронирование'
        verbose_name_plural = 'Заявки на бронирование'
        ordering = ['-created_at']

    def __str__(self):
        return f'Бронь #{self.pk} — {self.client} — {self.product}'
