# apps/rental/admin.py
from django.contrib import admin
from .models import RentalOrder, OrderItem, ReturnDocument, ReturnItem, Payment, OrderExcludedDay


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['original_total_cost', 'current_total_cost', 'quantity_returned', 'quantity_remaining']


class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 0
    readonly_fields = ['actual_days', 'actual_hours', 'calculated_cost']


@admin.register(RentalOrder)
class RentalOrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'status', 'order_code', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['client__last_name', 'id', 'order_code']
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity_taken', 'quantity_remaining', 'price_per_day', 'price_per_hour', 'original_total_cost', 'current_total_cost']
    list_filter = ['order__status']
    search_fields = ['product__name', 'order__client__last_name']
    readonly_fields = ['original_total_cost', 'current_total_cost']


@admin.register(ReturnDocument)
class ReturnDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'return_date', 'get_total_cost_display']
    list_filter = ['return_date']
    inlines = [ReturnItemInline]

    def get_total_cost_display(self, obj):
        return f"{obj.get_total_cost():.0f} сом"
    get_total_cost_display.short_description = 'Сумма'


@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'return_document', 'order_item', 'quantity', 'actual_days', 'actual_hours', 'calculated_cost', 'repair_fee']
    list_filter = ['return_document__return_date']
    readonly_fields = ['actual_days', 'actual_hours', 'calculated_cost']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['client', 'amount', 'payment_method', 'payment_date']
    list_filter = ['payment_method', 'payment_date']
    search_fields = ['client__last_name']


@admin.register(OrderExcludedDay)
class OrderExcludedDayAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'order_item', 'date', 'created_at']
    list_filter = ['date']
    search_fields = ['order__client__last_name']
