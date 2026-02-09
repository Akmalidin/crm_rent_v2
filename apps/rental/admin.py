# apps/rental/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import RentalOrder, OrderItem, ReturnDocument, ReturnItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['original_total_cost', 'current_total_cost', 'quantity_returned', 'quantity_remaining']


@admin.register(RentalOrder)
class RentalOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'created_at', 'status', 'get_current_total_display']
    list_filter = ['status', 'created_at']
    search_fields = ['client__first_name', 'client__last_name']
    inlines = [OrderItemInline]
    
    def get_current_total_display(self, obj):
        return f"{obj.get_current_total():.0f} сом"
    get_current_total_display.short_description = 'Сумма'


@admin.register(ReturnDocument)
class ReturnDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'return_date', 'get_total_items', 'get_total_cost_display']
    list_filter = ['return_date']
    
    def get_total_cost_display(self, obj):
        return f"{obj.get_total_cost():.0f} сом"
    get_total_cost_display.short_description = 'Сумма'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['client', 'amount_display', 'payment_date', 'payment_method']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['client__first_name', 'client__last_name']
    
    def amount_display(self, obj):
        return f"{obj.amount:.0f} сом"
    amount_display.short_description = 'Сумма'