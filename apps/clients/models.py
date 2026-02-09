from django.db import models
from django.core.validators import RegexValidator
from django.db.models import Sum
import os

def passport_front_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f'passports/{instance.last_name}_{instance.first_name}/front{ext}'

def passport_back_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f'passports/{instance.last_name}_{instance.first_name}/back{ext}'

class Client(models.Model):
    last_name = models.CharField('Фамилия', max_length=100)
    first_name = models.CharField('Имя', max_length=100)
    middle_name = models.CharField('Отчество', max_length=100, blank=True)
    passport_front = models.ImageField('Паспорт (лицевая)', upload_to=passport_front_path)
    passport_back = models.ImageField('Паспорт (обратная)', upload_to=passport_back_path)
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
        return float(total or 0)
    
    def get_total_debt(self):
        """Сколько всего должен"""
        total = 0
        for order in self.rental_orders.all():
            total += float(order.get_current_total())
        return total
    
    def get_wallet_balance(self):
        """Баланс кошелька (+ переплата, - долг)"""
        return self.get_total_paid() - self.get_total_debt()
    
    def get_debt(self):
        """Только долг (если баланс отрицательный)"""
        balance = self.get_wallet_balance()
        return abs(balance) if balance < 0 else 0
    
    def get_credit(self):
        """Только переплата (если баланс положительный)"""
        balance = self.get_wallet_balance()
        return balance if balance > 0 else 0
    
    def has_debt(self):
        """Есть ли долг"""
        return self.get_wallet_balance() < 0
    
    def has_credit(self):
        """Есть ли переплата"""
        return self.get_wallet_balance() > 0
    
    def get_active_orders(self):
        """Активные заказы (не закрытые)"""
        return self.rental_orders.filter(status='open')

class ClientPhone(models.Model):
    phone_regex = RegexValidator(regex=r'^\+?996?\d{9,12}$')
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='phones')
    phone_number = models.CharField('Номер', validators=[phone_regex], max_length=17)
    is_primary = models.BooleanField('Основной', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Телефон'
        verbose_name_plural = 'Телефоны'
    
    def __str__(self):
        return self.phone_number