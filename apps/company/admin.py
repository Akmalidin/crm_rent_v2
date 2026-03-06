# apps/company/admin.py
from django.contrib import admin
from .models import CompanyProfile


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'short_name', 'phone', 'city', 'currency', 'created_by']
    search_fields = ['company_name', 'short_name', 'inn']
    fieldsets = (
        ('Основное', {
            'fields': ('company_name', 'short_name', 'logo', 'currency')
        }),
        ('Контакты', {
            'fields': ('phone', 'email', 'website', 'address', 'city')
        }),
        ('Реквизиты', {
            'fields': ('inn', 'bank_account', 'bank_name'),
            'classes': ('collapse',)
        }),
        ('Прочее', {
            'fields': ('footer_text', 'created_by'),
            'classes': ('collapse',)
        }),
    )
