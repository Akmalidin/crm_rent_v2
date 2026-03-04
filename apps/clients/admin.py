# apps/clients/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Client, ClientPhone


class ClientPhoneInline(admin.TabularInline):
    model = ClientPhone
    extra = 1
    fields = ['phone_number', 'is_primary']


@admin.register(ClientPhone)
class PhoneAdmin(admin.ModelAdmin):
    list_display = ['client', 'phone_number', 'is_primary']
    search_fields = ['phone_number', 'client__last_name']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'telegram_id', 'created_at']
    search_fields = ['last_name', 'first_name', 'middle_name']
    list_filter = ['created_at']
    inlines = [ClientPhoneInline]
    fieldsets = (
        ('Основная информация', {
            'fields': ('last_name', 'first_name', 'middle_name')
        }),
        ('Telegram', {
            'fields': ('telegram_id',),
            'description': 'Telegram ID для отправки уведомлений. '
                          'Клиент получает его написав боту команду /start или /myid'
        }),
    )
