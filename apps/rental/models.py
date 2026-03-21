# apps/rental/models.py
from django.db import models
from django.utils import timezone
from django.db.models import Sum
from apps.clients.models import Client
from apps.inventory.models import Product
from decimal import Decimal
import math

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

    proof_file = models.FileField(
        'Доказательство (фото/аудио)',
        upload_to='orders/proofs/',
        blank=True,
        null=True
    )

    has_delivery = models.BooleanField('Доставка', default=False)
    delivery_address = models.CharField('Адрес доставки', max_length=500, blank=True)
    delivery_vehicle = models.CharField('Автомобиль', max_length=200, blank=True)
    delivery_plate = models.CharField('Номер авто', max_length=50, blank=True)
    delivery_cost = models.DecimalField('Стоимость доставки', max_digits=10, decimal_places=2, default=0)

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
    
    def get_current_total(self):
        """Получить текущую стоимость заказа с учётом просрочки"""
        total = Decimal('0')
        for item in self.items.all():
            total += item.get_actual_cost()
        return total
    
    def get_original_total(self):
        """Получить оригинальную стоимость заказа (БЕЗ просрочки)"""
        total = Decimal('0')
        for item in self.items.all():
            total += Decimal(str(item.original_total_cost))
        return total

    def get_saved_amount(self):
        """Экономия от досрочного возврата"""
        return self.get_original_total() - self.get_current_total()

    def get_rain_excluded_count(self):
        """Количество (товар, дата) пар исключённых дождём"""
        return self.excluded_days.count()

    def get_total_excluding_rain(self):
        """Итого с учётом дождливых дней по каждому товару отдельно"""
        has_any = self.excluded_days.exists()
        if not has_any:
            return self.get_current_total()
        total = Decimal('0')
        for item in self.items.all():
            total += item.get_cost_excluding_rain()
        return total
    
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
    rain_applicable = models.BooleanField('Дождь не считается', default=False)

    class Meta:
        verbose_name = 'Товар в заказе'
        verbose_name_plural = 'Товары в заказе'
    
    def __str__(self):
        return f"{self.product.name} ({self.quantity_taken} шт)"
    
    def calculate_cost_from_duration(self, days, hours, quantity):
        """
        Рассчитать стоимость на основе дней, часов и количества
        
        Args:
            days: количество дней аренды
            hours: количество часов аренды
            quantity: количество единиц товара
            
        Returns:
            Decimal: стоимость
        """
        price_per_day = Decimal(str(self.price_per_day))
        price_per_hour = Decimal(str(self.price_per_hour))
        
        # Если нет цены за час, считаем как price_per_day / 24
        if price_per_hour == 0:
            price_per_hour = price_per_day / 24
        
        days_cost = Decimal(str(days)) * price_per_day * Decimal(str(quantity))
        hours_cost = Decimal(str(hours)) * price_per_hour * Decimal(str(quantity))
        
        return days_cost + hours_cost
    
    def calculate_original_cost(self):
        """Рассчитать оригинальную стоимость"""
        return self.calculate_cost_from_duration(
            self.rental_days, 
            self.rental_hours, 
            self.quantity_taken
        )
    
    def get_cost_excluding_rain(self):
        """Стоимость позиции с учётом своих дождливых дней (per-item).

        Дождь снижает только БАЗОВУЮ стоимость аренды пропорционально.
        Штраф за просрочку остаётся — дождь не отменяет обязанность вернуть товар.
        """
        actual = self.get_actual_cost()
        excluded_count = self.excluded_days.count()

        if excluded_count == 0:
            return actual

        base = Decimal(str(self.original_total_cost))
        total_hours = Decimal(str(self.rental_days)) * 24 + Decimal(str(self.rental_hours))

        if total_hours <= 0:
            return actual

        excluded_hours = Decimal(str(excluded_count)) * 24
        billed_hours = max(Decimal('0'), total_hours - excluded_hours)

        reduced_base = (billed_hours / total_hours) * base
        overdue = actual - base  # штраф за просрочку

        return reduced_base + max(Decimal('0'), overdue)

    def recalculate_from_dates(self):
        """
        Пересчитать rental_days, rental_hours и стоимость на основе дат
        
        Используется при изменении planned_return_date
        """
        if not self.issued_date or not self.planned_return_date:
            return
        
        # Вычисляем разницу
        time_diff = self.planned_return_date - self.issued_date
        total_seconds = max(0, time_diff.total_seconds())

        # Если у товара нет цены за час, аренда считается ТОЛЬКО по дням:
        # любое положительное время = минимум 1 день, округляем вверх по суткам.
        product_hour_price = getattr(self.product, 'price_per_hour', None)
        is_daily_pricing = not (product_hour_price and product_hour_price > 0)

        if is_daily_pricing:
            self.rental_days = max(1, int(math.ceil(total_seconds / 86400))) if total_seconds > 0 else 0
            self.rental_hours = 0
        else:
            # Почасовая тарификация: округляем вверх до часа, чтобы не получать 0 при 10-30 мин.
            total_hours = int(math.ceil(total_seconds / 3600)) if total_seconds > 0 else 0
            self.rental_days = total_hours // 24
            self.rental_hours = total_hours % 24
        
        # Пересчитываем стоимость
        self.original_total_cost = self.calculate_original_cost()
        self.current_total_cost = self.original_total_cost
    
    
    def save(self, *args, **kwargs):
        if not self.pk:  # ТОЛЬКО при создании
            self.quantity_remaining = self.quantity_taken
            if not self.original_total_cost:
                self.original_total_cost = self.calculate_original_cost()
            if not self.current_total_cost:
                self.current_total_cost = self.original_total_cost
        
        # При обновлении НИЧЕГО не пересчитываем автоматически!
        super().save(*args, **kwargs)
    
    def get_actual_cost(self):
        """
        Актуальная стоимость позиции:
        - возвращённые штуки: по факту (actual_days × price + repair_fee из ReturnItem)
        - оставшиеся штуки: по плану + штраф за просрочку (если есть)
        """
        now = timezone.now()
        price_per_day = Decimal(str(self.price_per_day))

        # Сумма уже возвращённых штук (использует prefetch-кеш если есть, иначе aggregate)
        if hasattr(self, '_prefetched_objects_cache') and 'returns' in self._prefetched_objects_cache:
            returned_actual = sum(r.calculated_cost for r in self.returns.all()) or Decimal('0')
        else:
            returned_actual = self.returns.aggregate(t=Sum('calculated_cost'))['t'] or Decimal('0')
        returned_actual = Decimal(str(returned_actual))

        # Все штуки возвращены — только фактические затраты
        if self.quantity_remaining == 0:
            return returned_actual

        # Плановая стоимость оставшихся штук
        remaining_base = price_per_day * Decimal(str(self.quantity_remaining)) * Decimal(str(self.rental_days))

        # Нет просрочки
        if self.planned_return_date >= now:
            return returned_actual + remaining_base

        # Просрочка — доплата только за оставшиеся штуки
        overdue_time = now - self.planned_return_date
        if overdue_time.total_seconds() < 86400:
            overdue_cost = (price_per_day / 24) * Decimal(str(overdue_time.seconds // 3600)) * Decimal(str(self.quantity_remaining))
        else:
            overdue_cost = price_per_day * Decimal(str(overdue_time.days)) * Decimal(str(self.quantity_remaining))

        return returned_actual + remaining_base + overdue_cost
    
    @property
    def is_overdue(self):
        """Проверка просрочен ли товар"""
        return self.quantity_remaining > 0 and self.planned_return_date < timezone.now()
    
    @property
    def overdue_days(self):
        """Количество дней просрочки"""
        if not self.is_overdue:
            return 0
        overdue_time = timezone.now() - self.planned_return_date
        return overdue_time.days
    
    @property
    def overdue_hours(self):
        """Количество часов просрочки (остаток)"""
        if not self.is_overdue:
            return 0
        overdue_time = timezone.now() - self.planned_return_date
        return overdue_time.seconds // 3600
    
    @property
    def overdue_cost(self):
        """Стоимость просрочки"""
        if not self.is_overdue:
            return Decimal('0')
        
        return self.get_actual_cost() - Decimal(str(self.original_total_cost))



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
        return total or Decimal('0')


class ReturnItem(models.Model):
    """Товар в возврате"""

    return_document = models.ForeignKey(ReturnDocument, on_delete=models.CASCADE, related_name='items', verbose_name='Документ возврата')
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name='returns', verbose_name='Товар из заказа')

    quantity = models.PositiveIntegerField('Возвращено штук')
    actual_days = models.PositiveIntegerField('Фактически дней')
    actual_hours = models.PositiveIntegerField('Фактически часов', default=0)
    calculated_cost = models.DecimalField('Стоимость по факту', max_digits=10, decimal_places=2)
    notes = models.TextField('Примечания', blank=True)
    repair_fee = models.DecimalField('Плата за ремонт/чистку', max_digits=10, decimal_places=2, default=0)
    repair_notes = models.TextField('Примечание по ремонту', blank=True)
    
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
        # Если товар тарифицируется по дням (нет цены за час),
        # округляем вверх до полных суток, часы не считаем
        if self.order_item.price_per_hour == 0 and self.actual_hours > 0:
            self.actual_days += 1
            self.actual_hours = 0
    
    def calculate_cost(self):
        base = self.quantity * (
            self.order_item.price_per_day * self.actual_days +
            self.order_item.price_per_hour * self.actual_hours
        )
        return base + (self.repair_fee or Decimal('0'))
    
    def save(self, *args, **kwargs):
        self.calculate_actual_time()
        self.calculated_cost = self.calculate_cost()

        self.order_item.quantity_returned += self.quantity
        self.order_item.quantity_remaining -= self.quantity

        # Накопленная стоимость предыдущих возвратов (до сохранения текущего)
        prev_returned = self.order_item.returns.aggregate(t=Sum('calculated_cost'))['t'] or Decimal('0')
        prev_returned = Decimal(str(prev_returned))
        total_returned = prev_returned + Decimal(str(self.calculated_cost))

        # Плановая стоимость оставшихся штук (по исходной ставке)
        cost_per_item_plan = Decimal(str(self.order_item.original_total_cost)) / self.order_item.quantity_taken
        remaining_cost = cost_per_item_plan * self.order_item.quantity_remaining

        self.order_item.current_total_cost = total_returned + remaining_cost

        self.order_item.save()
        self.order_item.product.quantity_available += self.quantity
        self.order_item.product.save()

        super().save(*args, **kwargs)


class Payment(models.Model):
    """Оплата"""
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Наличные'),
        ('card', 'Карта'),
        ('transfer', 'Перевод'),
        ('credit', 'Зачёт аванса'),
        ('writeoff', 'Списание долга'),
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

class OrderExcludedDay(models.Model):
    """Дождливый/исключённый день аренды — за этот день деньги не считаются (per-item)"""
    order = models.ForeignKey(
        RentalOrder, on_delete=models.CASCADE,
        related_name='excluded_days',
        verbose_name='Заказ',
    )
    order_item = models.ForeignKey(
        'OrderItem', on_delete=models.CASCADE,
        related_name='excluded_days',
        verbose_name='Позиция заказа',
        null=True, blank=True,
    )
    date = models.DateField('Дата')
    created_at = models.DateTimeField('Добавлено', auto_now_add=True)

    class Meta:
        unique_together = [('order_item', 'date')]
        ordering = ['date']
        verbose_name = 'Исключённый день'
        verbose_name_plural = 'Исключённые дни (дождь)'

    def __str__(self):
        item_name = self.order_item.product.name if self.order_item_id else '—'
        return f"{self.order.order_code} / {item_name} — {self.date}"

class OrderAttachment(models.Model):
    """Файлы прикреплённые к заказу"""
    order      = models.ForeignKey(RentalOrder, on_delete=models.CASCADE, related_name='attachments', verbose_name='Заказ')
    file       = models.FileField('Файл', upload_to='orders/attachments/')
    name       = models.CharField('Название', max_length=255)
    uploaded_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='order_attachments', verbose_name='Загрузил',
    )
    uploaded_at = models.DateTimeField('Дата загрузки', auto_now_add=True)

    class Meta:
        verbose_name = 'Файл заказа'
        verbose_name_plural = 'Файлы заказов'
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.name

    @property
    def is_image(self):
        ext = self.name.rsplit('.', 1)[-1].lower() if '.' in self.name else ''
        return ext in ('jpg', 'jpeg', 'png', 'gif', 'webp')

    @property
    def icon(self):
        ext = self.name.rsplit('.', 1)[-1].lower() if '.' in self.name else ''
        icons = {'pdf': 'pdf', 'doc': 'doc', 'docx': 'doc', 'xls': 'xls', 'xlsx': 'xls'}
        return icons.get(ext, 'file')
