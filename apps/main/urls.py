from django.urls import path
from . import telegram_webhook_complete, views, reports_views, pdf_views
app_name = 'main'
urlpatterns = [
    # Главная
    path('', views.dashboard, name='dashboard'),
    path('history/', views.history, name='history'),
    path('search/', views.global_search, name='global_search'),
    path('telegram/webhook/', telegram_webhook_complete.telegram_webhook, name='telegram_webhook'),
    
    # Клиенты
    path('clients/', views.clients_list, name='clients_list'),
    path('clients/<int:client_id>/', views.client_detail, name='client_detail'),
    
    
    # Заказы
    path('rental/orders/', views.orders_list, name='orders_list'),
    path('rental/create/', views.create_order, name='create_order'),
    path('rental/returns/', views.returns_page, name='returns_page'),
    path('rental/orders/<int:order_id>/edit/', views.edit_order, name='edit_order'),
    path('rental/items/<int:item_id>/edit-date/', views.edit_order_item_date, name='edit_item_date'),

    
    # Оплаты
    path('payment/', views.accept_payment, name='accept_payment'),
    path('orders/<int:order_id>/apply-credit/', views.apply_credit_to_order, name='apply_credit_to_order'),
    path('orders/<int:order_id>/close/', views.close_order, name='close_order'),
    
    # Отчёты
    path('reports/', reports_views.reports_main, name='reports_main'),
    path('reports/monthly/', reports_views.reports_monthly, name='reports_monthly'),
    path('reports/clients/', reports_views.reports_clients, name='reports_clients'),
    path('reports/products/', reports_views.reports_products, name='reports_products'),
    path('reports/financial/', reports_views.reports_financial, name='reports_financial'),

    path('orders/<int:order_id>/print/contract/', pdf_views.print_contract, name='print_contract'),
    path('orders/<int:order_id>/print/acceptance/', pdf_views.print_acceptance, name='print_acceptance'),
    path('orders/<int:order_id>/print/return/', pdf_views.print_return, name='print_return'),
    path('payments/<int:payment_id>/print/receipt/', pdf_views.print_receipt, name='print_receipt'),
    path('orders/<int:order_id>/notify/', views.send_overdue_notification, name='send_notification'),

]