# apps/rental/models.py
from django.db import models
from django.utils import timezone
from django.db.models import Sum
from apps.clients.models import Client
from apps.inventory.models import Product


class RentalOrder(models.Model):
    """Заказ аренды"""
    
    STATUS_CHOICES = [
        ('open', 'Открыт'),
        ('closed', 'Закрыт'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='rental_orders', verbose_name='Клиент')
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='open')
    notes = models.TextField('Примечания', blank=True)
    
    order_number = models.PositiveIntegerField(
        verbose_name='Номер заказа клиента',
        help_text='Порядковый номер заказа для этого клиента (#1, #2, #3...)',
        null=True,
        blank=True
    )
    
    order_code = models.CharField(
        max_length=50,
        verbose_name='Код заказа',
        help_text='Уникальный код заказа (ФИО-1, ФИО-2...)',
        blank=True,
        db_index=True
    )


    class Meta:
        verbose_name = 'Заказ аренды'
        verbose_name_plural = 'Заказы аренды'
        ordering = ['-created_at']
    
    def __str__(self):
        if self.order_code:
            return f"Заказ {self.order_code} - {self.client.get_full_name()}"
        return f"Заказ #{self.id} - {self.client.get_full_name()}"
    
    def save(self, *args, **kwargs):
        # Автоматическая генерация номера и кода при создании
        if not self.pk:  # Только для новых заказов
            self.generate_order_number_and_code()
        super().save(*args, **kwargs)
    
    def generate_order_number_and_code(self):
        """С проверкой на уникальность"""
        
        # Получаем количество с блокировкой
        from django.db import transaction
        
        with transaction.atomic():
            client_orders = RentalOrder.objects.filter(
                client=self.client
            ).select_for_update()
            
            client_orders_count = client_orders.count()
            self.order_number = client_orders_count + 1
            
            # Генерируем код
            last_name = self.client.last_name.upper()[:3]
            self.order_code = f"{last_name}-{self.order_number}"
            
            # Проверяем уникальность кода (на всякий случай)
            while RentalOrder.objects.filter(order_code=self.order_code).exists():
                self.order_number += 1
                self.order_code = f"{last_name}-{self.order_number}"
            

    def get_display_name(self):
        """Красивое отображение заказа"""
        if self.order_code:
            return f"#{self.order_number} ({self.order_code})"
        return f"#{self.id}"
    
    def get_original_total(self):
        """Изначальная сумма"""
        total = self.items.aggregate(total=Sum('original_total_cost'))['total']
        return float(total or 0)
    
    def get_current_total(self):
        "Текущая стоимость заказа с учётом возвратов и просрочки"
        from decimal import Decimal
        
        total = Decimal('0')
        
        for item in self.items.all():
            # Используем метод get_actual_cost который учитывает всё
            total += item.get_actual_cost()
        
        return total

    def get_saved_amount(self):
        """Экономия от досрочного возврата"""
        return self.get_original_total() - self.get_current_total()
    
    def has_unreturned_items(self): 
        """Есть ли невозвращённые товары"""
        return self.items.filter(quantity_remaining__gt=0).exists()
    
    def update_status(self):
        """Обновить статус"""
        if not self.has_unreturned_items():
            self.status = 'closed'
        else:
            self.status = 'open'
        self.save()


class OrderItem(models.Model):
    """Товар в заказе"""
    
    order = models.ForeignKey(RentalOrder, on_delete=models.CASCADE, related_name='items', verbose_name='Заказ')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name='Товар')
    
    quantity_taken = models.PositiveIntegerField('Взято штук')
    quantity_returned = models.PositiveIntegerField('Возвращено штук', default=0)
    quantity_remaining = models.PositiveIntegerField('Осталось штук')
    
    issued_date = models.DateTimeField('Дата выдачи')
    planned_return_date = models.DateTimeField('Планируемая дата возврата')
    
    rental_days = models.PositiveIntegerField('Дней аренды', default=1)
    rental_hours = models.PositiveIntegerField('Часов аренды', default=0)
    
    price_per_day = models.DecimalField('Цена/день', max_digits=10, decimal_places=2)
    price_per_hour = models.DecimalField('Цена/час', max_digits=10, decimal_places=2, default=0)
    
    original_total_cost = models.DecimalField('Изначальная стоимость', max_digits=10, decimal_places=2)
    current_total_cost = models.DecimalField('Текущая стоимость', max_digits=10, decimal_places=2)
    actual_cost = models.DecimalField('Фактическая стоимость', max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Товар в заказе'
        verbose_name_plural = 'Товары в заказе'
    
    def __str__(self):
        return f"{self.product.name} ({self.quantity_taken} шт)"
    
    def calculate_original_cost(self):
        return float(self.quantity_taken * (float(self.price_per_day) * self.rental_days + float(self.price_per_hour) * self.rental_hours))
    
    def save(self, *args, **kwargs):
        if not self.pk:
            self.quantity_remaining = self.quantity_taken
            if not self.original_total_cost:
                self.original_total_cost = self.calculate_original_cost()
            if not self.current_total_cost:
                self.current_total_cost = self.original_total_cost
        super().save(*args, **kwargs)
    
    def get_actual_cost(self):
        '''Фактическая стоимость с учётом возвратов и просрочки'''
        from decimal import Decimal
        
        # Если всё возвращено - используем сохранённую фактическую стоимость
        if self.quantity_remaining == 0:
            if self.actual_cost is not None:
                return Decimal(str(self.actual_cost))
            # Fallback если actual_cost не сохранён
            return Decimal(str(self.current_total_cost))
        
        # Если есть невозвращённые товары
        if self.quantity_remaining > 0:
            now = timezone.now()
            
            # Стоимость возвращённых товаров (если есть)
            returned_qty = self.quantity_taken - self.quantity_remaining
            returned_cost = Decimal('0')
            
            if returned_qty > 0 and self.actual_cost is not None:
                # Пропорционально от фактической стоимости возвращённых
                cost_per_item = Decimal(str(self.actual_cost)) / self.quantity_taken
                returned_cost = cost_per_item * returned_qty
            
            # Стоимость невозвращённых товаров
            unreturned_cost = Decimal('0')
            
            # Если просрочено
            if now > self.planned_return_date:
                overdue_time = now - self.planned_return_date
                
                # Плановая стоимость оставшихся товаров
                cost_per_item = Decimal(str(self.current_total_cost)) / self.quantity_taken
                planned_cost = cost_per_item * self.quantity_remaining
                
                # Стоимость просрочки
                if overdue_time.total_seconds() < 86400:  # Меньше суток
                    overdue_hours = overdue_time.total_seconds() / 3600
                    hourly_rate = Decimal(str(self.price_per_day)) / 24
                    overdue_cost = Decimal(str(overdue_hours)) * hourly_rate * self.quantity_remaining
                else:
                    overdue_days = overdue_time.days
                    overdue_cost = Decimal(str(overdue_days)) * Decimal(str(self.price_per_day)) * self.quantity_remaining
                
                unreturned_cost = planned_cost + overdue_cost
            else:
                # Ещё не просрочено - плановая стоимость
                cost_per_item = Decimal(str(self.current_total_cost)) / self.quantity_taken
                unreturned_cost = cost_per_item * self.quantity_remaining
            
            return returned_cost + unreturned_cost
        
        return Decimal(str(self.current_total_cost))


class ReturnDocument(models.Model):
    """Документ возврата"""
    
    return_date = models.DateTimeField('Дата возврата', default=timezone.now)
    notes = models.TextField('Примечания', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Возврат'
        verbose_name_plural = 'Возвраты'
        ordering = ['-return_date']
    
    def __str__(self):
        return f"Возврат #{self.id}"
    
    def get_total_items(self):
        total = self.items.aggregate(total=Sum('quantity'))['total']
        return total or 0
    
    def get_total_cost(self):
        total = self.items.aggregate(total=Sum('calculated_cost'))['total']
        return float(total or 0)


class ReturnItem(models.Model):
    """Товар в возврате"""
    
    return_document = models.ForeignKey(ReturnDocument, on_delete=models.CASCADE, related_name='items', verbose_name='Документ возврата')
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name='returns', verbose_name='Товар из заказа')
    
    quantity = models.PositiveIntegerField('Возвращено штук')
    actual_days = models.PositiveIntegerField('Фактически дней')
    actual_hours = models.PositiveIntegerField('Фактически часов', default=0)
    calculated_cost = models.DecimalField('Стоимость по факту', max_digits=10, decimal_places=2)
    notes = models.TextField('Примечания', blank=True)
    
    class Meta:
        verbose_name = 'Товар в возврате'
        verbose_name_plural = 'Товары в возврате'
    
    def __str__(self):
        return f"{self.order_item.product.name} ({self.quantity} шт)"
    
    def calculate_actual_time(self):
        delta = self.return_document.return_date - self.order_item.issued_date
        total_seconds = delta.total_seconds()
        self.actual_days = int(total_seconds // 86400)
        remaining_seconds = total_seconds % 86400
        self.actual_hours = int(remaining_seconds // 3600)
    
    def calculate_cost(self):
        return float(self.quantity * (float(self.order_item.price_per_day) * self.actual_days + float(self.order_item.price_per_hour) * self.actual_hours))
    
    def save(self, *args, **kwargs):
        self.calculate_actual_time()
        self.calculated_cost = self.calculate_cost()
        
        self.order_item.quantity_returned += self.quantity
        self.order_item.quantity_remaining -= self.quantity
        
        if self.order_item.quantity_remaining == 0:
            self.order_item.current_total_cost = self.calculated_cost
        else:
            returned_cost = self.calculated_cost
            cost_per_item_plan = float(self.order_item.original_total_cost) / self.order_item.quantity_taken
            remaining_cost = cost_per_item_plan * self.order_item.quantity_remaining
            self.order_item.current_total_cost = returned_cost + remaining_cost
        
        self.order_item.save()
        self.order_item.product.quantity_available += self.quantity
        self.order_item.product.save()
        self.order_item.order.update_status()
        
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Оплата"""
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Наличные'),
        ('card', 'Карта'),
        ('transfer', 'Перевод'),
        ('credit', 'Зачёт аванса'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payments', verbose_name='Клиент')
    amount = models.DecimalField('Сумма', max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField('Дата оплаты', default=timezone.now)
    payment_method = models.CharField('Способ оплаты', max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    notes = models.TextField('Примечания', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Оплата'
        verbose_name_plural = 'Оплаты'
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"{self.amount} сом - {self.client.get_full_name()}"