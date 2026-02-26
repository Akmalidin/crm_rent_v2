from django.db import models
from django.contrib.auth.models import User

class CompanyProfile(models.Model):
    """Профиль компании (один на всю систему)"""
    
    # Основная информация
    company_name = models.CharField(
        max_length=255,
        verbose_name='Название компании',
        help_text='Полное название вашей компании'
    )
    
    short_name = models.CharField(
        max_length=100,
        verbose_name='Короткое название',
        blank=True,
        help_text='Для использования в документах'
    )
    
    # Контактная информация
    phone = models.CharField(max_length=50, verbose_name='Телефон', blank=True)
    email = models.EmailField(verbose_name='Email', blank=True)
    website = models.URLField(verbose_name='Веб-сайт', blank=True)
    
    # Адрес
    address = models.TextField(verbose_name='Адрес', blank=True)
    city = models.CharField(max_length=100, verbose_name='Город', blank=True)
    
    # Реквизиты
    inn = models.CharField(max_length=50, verbose_name='ИНН', blank=True)
    bank_account = models.CharField(max_length=100, verbose_name='Расчётный счёт', blank=True)
    bank_name = models.CharField(max_length=255, verbose_name='Название банка', blank=True)
    
    # Логотип
    logo = models.ImageField(
        upload_to='company_logos/',
        verbose_name='Логотип',
        blank=True,
        null=True
    )
    
    # Дополнительные настройки
    currency = models.CharField(
        max_length=10,
        verbose_name='Валюта',
        default='сом',
        help_text='Название валюты для документов'
    )
    
    # Для печати документов
    footer_text = models.TextField(
        verbose_name='Текст в подвале документов',
        blank=True,
        help_text='Будет отображаться внизу договоров и чеков'
    )
    
    # Служебные поля
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_company'
    )
    
    class Meta:
        verbose_name = 'Профиль компании'
        verbose_name_plural = 'Профили компании'
    
    def __str__(self):
        return self.company_name
    
    @classmethod
    def get_company(cls):
        """Получить единственный профиль компании"""
        company, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'company_name': 'Моя компания',
                'currency': 'сом',
            }
        )
        return company
    
    def save(self, *args, **kwargs):
        # Убеждаемся что это единственная запись
        self.pk = 1
        super().save(*args, **kwargs)