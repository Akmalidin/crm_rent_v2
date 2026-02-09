# apps/main/urls.py - ОБНОВЛЁННАЯ ВЕРСИЯ
# Замените весь файл на этот:

from django.urls import path
from . import views
from . import reports_views

app_name = 'main'

urlpatterns = [
    # Главная
    path('', views.dashboard, name='dashboard'),
    path('history/', views.history, name='history'),
    
    # Клиенты
    path('clients/', views.clients_list, name='clients_list'),
    path('clients/<int:client_id>/', views.client_detail, name='client_detail'),
    
    # Заказы
    path('rental/orders/', views.orders_list, name='orders_list'),
    path('rental/create/', views.create_order, name='create_order'),
    path('rental/returns/', views.returns_page, name='returns_page'),
    
    # Оплаты
    path('payment/', views.accept_payment, name='accept_payment'),
    
    # Отчёты
    path('reports/', reports_views.reports_main, name='reports_main'),
    path('reports/monthly/', reports_views.reports_monthly, name='reports_monthly'),
    path('reports/clients/', reports_views.reports_clients, name='reports_clients'),
    path('reports/products/', reports_views.reports_products, name='reports_products'),
    path('reports/financial/', reports_views.reports_financial, name='reports_financial'),
]