# apps/inventory/admin.py
from django.contrib import admin
from .models import Category, Product, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner']
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'warehouse', 'quantity_total', 'quantity_available', 'price_per_day', 'price_per_hour', 'is_active']
    list_filter = ['category', 'is_active', 'warehouse']
    search_fields = ['name']
