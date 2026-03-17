from django.db import models
from django.core.validators import RegexValidator
from django.db.models import Sum
from django.contrib.auth.models import User
import os

def passport_front_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f'passports/{instance.last_name}_{instance.first_name}/front{ext}'

def passport_back_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f'passports/{instance.last_name}_{instance.first_name}/back{ext}'

class Client(models.Model):
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='clients',
        verbose_name='Компания (владелец)',
    )
    last_name = models.CharField('Фамилия', max_length=100)
    first_name = models.CharField('Имя', max_length=100)
    middle_name = models.CharField('Отчество', max_length=100, blank=True)
    passport_front = models.ImageField('Паспорт (лицевая)', upload_to=passport_front_path, blank=True, null=True)
    passport_back = models.ImageField('Паспорт (обратная)', upload_to=passport_back_path, blank=True, null=True)
    email = models.EmailField('Email', blank=True, null=True)
    telegram_id = models.CharField(max_length=50, blank=True, null=True, verbose_name='Telegram ID')
    created_at = models.DateTimeField('Дата регистрации', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.get_full_name()
    
    def get_full_name(self):
        return f"{self.last_name} {self.first_name} {self.middle_name}".strip()
    
    def get_total_paid(self):
        """Сколько всего оплатил"""
        total = self.payments.aggregate(total=Sum('amount'))['total']
        return round(float(total or 0), 2)

    def get_total_debt(self):
        """Сколько всего должен"""
        total = 0
        for order in self.rental_orders.all():
            total += float(order.get_current_total())
        return round(total, 2)

    def get_wallet_balance(self):
        """Баланс кошелька (+ переплата, - долг)"""
        return round(self.get_total_paid() - self.get_total_debt(), 2)

    def get_debt(self):
        """Только долг (если баланс отрицательный)"""
        balance = self.get_wallet_balance()
        return round(abs(balance), 2) if balance < -0.005 else 0

    def get_credit(self):
        """Только переплата (если баланс положительный)"""
        balance = self.get_wallet_balance()
        return round(balance, 2) if balance > 0.005 else 0

    def has_debt(self):
        """Есть ли долг"""
        return self.get_wallet_balance() < -0.005

    def has_credit(self):
        """Есть ли переплата"""
        return self.get_wallet_balance() > 0.005
    
    def get_active_orders(self):
        """Активные заказы (не закрытые)"""
        return self.rental_orders.filter(status='open')

    def get_rating(self):
        """
        Автоматический рейтинг клиента (0–100 баллов).
        Факторы:
          +20  нет долга
          -20  есть долг
          +15  >= 3 закрытых заказа (лояльный)
          +10  >= 1 закрытый заказ
          +15  нет просрочек (все возвращал вовремя)
          -15  есть просрочки
          +10  оплатил >= 10 000 сом суммарно
          +10  зарегистрирован > 30 дней
          +20  базовые баллы (новый клиент)
        """
        from django.utils import timezone
        score = 20  # базовые баллы

        # Долг
        balance = self.get_wallet_balance()
        if balance >= 0:
            score += 20
        else:
            score -= 20

        # Количество закрытых заказов
        closed = self.rental_orders.filter(status='closed').count()
        if closed >= 3:
            score += 15
        elif closed >= 1:
            score += 10

        # Просрочки
        now = timezone.now()
        has_overdue = False
        for order in self.rental_orders.filter(status='open'):
            for item in order.items.all():
                if item.quantity_remaining > 0 and item.planned_return_date < now:
                    has_overdue = True
                    break
            if has_overdue:
                break
        if has_overdue:
            score -= 15
        else:
            score += 15

        # Общая сумма оплат
        total_paid = self.get_total_paid()
        if total_paid >= 10000:
            score += 10

        # Время регистрации
        days_since = (now - self.created_at).days if self.created_at else 0
        if days_since > 30:
            score += 10

        return max(0, min(100, score))

    def get_rating_label(self):
        """Текстовая метка рейтинга."""
        r = self.get_rating()
        if r >= 80:
            return 'excellent'
        elif r >= 60:
            return 'good'
        elif r >= 40:
            return 'average'
        else:
            return 'poor'

    def get_rating_display(self):
        """Отображение рейтинга на русском."""
        labels = {
            'excellent': 'Отличный',
            'good': 'Хороший',
            'average': 'Средний',
            'poor': 'Низкий',
        }
        return labels.get(self.get_rating_label(), 'Нет данных')

class ClientProductDiscount(models.Model):
    """Скидка за 1 шт для постоянного клиента на конкретный товар"""
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='discounts',
        verbose_name='Клиент',
    )
    product = models.ForeignKey(
        'inventory.Product', on_delete=models.CASCADE, related_name='client_discounts',
        verbose_name='Товар',
    )
    discount_per_unit = models.DecimalField(
        'Скидка за 1 шт (сом)', max_digits=10, decimal_places=2, default=0,
    )
    notes = models.CharField('Примечание', max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Скидка клиента'
        verbose_name_plural = 'Скидки клиентов'
        unique_together = ('client', 'product')

    def __str__(self):
        return f'{self.client} — {self.product}: -{self.discount_per_unit} сом/шт'


class ClientPhone(models.Model):
    phone_regex = RegexValidator(regex=r'^\+(996\d{9}|7\d{10})$', message='Введите номер в формате +996XXXXXXXXX или +7XXXXXXXXXX')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='phones')
    phone_number = models.CharField('Номер', validators=[phone_regex], max_length=17)
    is_primary = models.BooleanField('Основной', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Телефон'
        verbose_name_plural = 'Телефоны'
    
    def __str__(self):
        return self.phone_number