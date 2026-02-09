# apps/clients/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Client, ClientPhone


class ClientPhoneInline(admin.TabularInline):
    """Телефоны клиента"""
    model = ClientPhone
    extra = 1
    fields = ['phone_number', 'is_primary']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Админка клиентов"""
    list_display = ['get_full_name', 'get_phones', 'get_balance_display', 'created_at']
    list_filter = ['created_at']
    search_fields = ['last_name', 'first_name', 'middle_name', 'phones__phone_number']
    inlines = [ClientPhoneInline]
    
    fieldsets = (
        ('Личные данные', {
            'fields': ('last_name', 'first_name', 'middle_name')
        }),
        ('Паспортные данные', {
            'fields': ('passport_front', 'passport_back')
        }),
        ('Финансы', {
            'fields': ('get_balance_info', 'get_debt_info'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'get_balance_info', 'get_debt_info']
    
    def get_phones(self, obj):
        """Отображение телефонов"""
        phones = obj.phones.all()
        return ', '.join([phone.phone_number for phone in phones]) if phones else '-'
    get_phones.short_description = 'Телефоны'
    
    def get_balance_display(self, obj):
        """Баланс кошелька в списке"""
        balance = obj.get_wallet_balance()
        if balance < 0:
            return format_html(
                '<span style="color: red; font-weight: bold;">-{} сом</span>',
                int(abs(balance))  # ← ИСПРАВЛЕНО
            )
        elif balance > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">+{} сом</span>',
                int(balance)  # ← ИСПРАВЛЕНО
            )
        return '0 сом'
    get_balance_display.short_description = '💰 Баланс'
    
    def get_balance_info(self, obj):
        """Баланс для просмотра в карточке"""
        balance = obj.get_wallet_balance()
        if balance < 0:
            return format_html(
                '<div style="font-size: 18px; color: red; font-weight: bold;">ДОЛГ: {} сом</div>',
                int(abs(balance))  # ← ИСПРАВЛЕНО
            )
        elif balance > 0:
            return format_html(
                '<div style="font-size: 18px; color: green; font-weight: bold;">ПЕРЕПЛАТА: {} сом</div>',
                int(balance)  # ← ИСПРАВЛЕНО
            )
        return format_html('<div style="font-size: 18px;">Баланс: 0 сом</div>')
    get_balance_info.short_description = '💰 Баланс кошелька'
    
    def get_debt_info(self, obj):
        """Детальная информация"""
        total_debt = obj.get_total_debt()
        total_paid = obj.get_total_paid()
        active_orders_count = obj.get_active_orders().count()
        
        return format_html(
            '<div style="line-height: 1.8;">'
            '<strong>Всего долг:</strong> {} сом<br>'
            '<strong>Всего оплачено:</strong> {} сом<br>'
            '<strong>Активных заказов:</strong> {}'
            '</div>',
            int(total_debt),      # ← ИСПРАВЛЕНО
            int(total_paid),      # ← ИСПРАВЛЕНО
            active_orders_count
        )
    get_debt_info.short_description = '📊 Детали'


@admin.register(ClientPhone)
class ClientPhoneAdmin(admin.ModelAdmin):
    """Админка телефонов"""
    list_display = ['phone_number', 'client', 'is_primary', 'created_at']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['phone_number', 'client__last_name', 'client__first_name']