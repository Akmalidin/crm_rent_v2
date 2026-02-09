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