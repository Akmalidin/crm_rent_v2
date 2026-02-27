from django.db import models

class Category(models.Model):
    name = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    
    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """Товар в инвентаре"""
    
    name = models.CharField('Название', max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    quantity_total = models.PositiveIntegerField('Всего', default=0)
    quantity_available = models.PositiveIntegerField('Доступно', default=0)
    price_per_day = models.DecimalField('Цена/день', max_digits=10, decimal_places=2)
    price_per_hour = models.DecimalField('Цена/час', max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField('Активен', default=True)
    
    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
    
    def __str__(self):
        return self.name
    
    def get_rented_quantity(self):
        """
        Получить количество товара в аренде
        
        Returns:
            int: количество единиц товара, которые сейчас в аренде
        """
        from apps.rental.models import OrderItem
        
        # Суммируем quantity_remaining из всех ОТКРЫТЫХ заказов
        rented = OrderItem.objects.filter(
            product=self,
            order__status='open'
        ).aggregate(
            total=models.Sum('quantity_remaining')
        )['total'] or 0
        
        return rented
    
    def get_available_quantity(self):
        """
        Получить РЕАЛЬНОЕ доступное количество
        
        Returns:
            int: количество единиц товара, доступных для аренды
        """
        return self.quantity_total - self.get_rented_quantity()
    
    def update_available_quantity(self):
        """
        Обновить quantity_available на основе реальных данных
        
        Вызывается при:
        - Создании/возврате аренды
        - Изменении quantity_total
        """
        self.quantity_available = self.get_available_quantity()
        self.save(update_fields=['quantity_available'])
    
    def save(self, *args, **kwargs):
        """
        Переопределённый save для валидации
        """
        # При создании товара quantity_available = quantity_total
        if not self.pk:
            self.quantity_available = self.quantity_total
        
        # Валидация: quantity_available не может быть больше quantity_total
        if self.quantity_available > self.quantity_total:
            self.quantity_available = self.quantity_total
        
        super().save(*args, **kwargs)
    
    @property
    def quantity_rented(self):
        """Сколько товара сейчас в аренде (для отображения)"""
        return self.get_rented_quantity()