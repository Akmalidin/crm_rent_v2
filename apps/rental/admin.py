# apps/rental/admin.py
from django.contrib import admin
from .models import RentalOrder, OrderItem, ReturnDocument, ReturnItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['original_total_cost', 'current_total_cost', 'quantity_returned', 'quantity_remaining']


@admin.register(RentalOrder)
class RentalOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['client__last_name', 'id']
    inlines = [OrderItemInline]


@admin.register(ReturnDocument)
class ReturnDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'return_date', 'get_total_cost_display']
    list_filter = ['return_date']

    def get_total_cost_display(self, obj):
        return f"{obj.get_total_cost():.0f} сом"
    get_total_cost_display.short_description = 'Сумма'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['client', 'amount', 'payment_method', 'payment_date']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['client__last_name']
