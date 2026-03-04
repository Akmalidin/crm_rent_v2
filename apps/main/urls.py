from django.urls import path
from . import telegram_webhook_complete, views, reports_views, pdf_views
from apps.clients import views as clients_views
from apps.inventory import views as inventory_views
from django.contrib.auth import views as auth_views

app_name = 'main'
urlpatterns = [
        # Авторизация
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register_view, name='register'),
    path('pending-approval/', views.pending_approval, name='pending_approval'),
    path('superadmin/', views.superuser_panel, name='superuser_panel'),
    
    # Настройка компании
    path('setup-company/', views.setup_company, name='setup_company'),
    path('company/edit/', views.edit_company, name='edit_company'),


    # Главная
    path('', views.dashboard, name='dashboard'),
    path('history/', views.history, name='history'),
    path('search/', views.global_search, name='global_search'),
    path('telegram/webhook/', telegram_webhook_complete.telegram_webhook, name='telegram_webhook'),
    path('calendar/', views.orders_calendar, name='calendar'),

    
    # Клиенты
    path('clients/', views.clients_list, name='clients_list'),
    path('clients/<int:client_id>/', views.client_detail, name='client_detail'),
    path('clients/create/', clients_views.create_client, name='create_client'),
    path('clients/<int:client_id>/edit/', clients_views.edit_client, name='edit_client'),
    path('clients/<int:client_id>/payments/', views.client_payments, name='client_payments'),

    
    
    # Заказы
    path('rental/orders/', views.orders_list, name='orders_list'),
    path('rental/create/', views.create_order, name='create_order'),
    path('rental/returns/', views.returns_page, name='returns_page'),
    path('rental/orders/<int:order_id>/edit/', views.edit_order, name='edit_order'),

    
    # Просмотр заказа (всё на одной странице)
    path('orders/<int:order_id>/', views.order_view, name='order_view'),

    # Оплаты
    path('payment/', views.accept_payment, name='accept_payment'),
    path('payment/client-orders/<int:client_id>/', views.client_orders_json, name='client_orders_json'),
    path('orders/<int:order_id>/apply-credit/', views.apply_credit_to_order, name='apply_credit_to_order'),
    path('orders/<int:order_id>/close/', views.close_order, name='close_order'),
    path('orders/<int:order_id>/excluded-days/', views.toggle_excluded_day, name='toggle_excluded_day'),
    path('rain-days/toggle/', views.toggle_rain_day, name='toggle_rain_day'),
    path('orders/<int:order_id>/edit-dates/', views.edit_order_dates_with_log, name='edit_order_dates'),
    
    # Отчёты
    path('reports/', reports_views.reports_main, name='reports_main'),
    path('reports/monthly/', reports_views.reports_monthly, name='reports_monthly'),
    path('reports/clients/', reports_views.reports_clients, name='reports_clients'),
    path('reports/products/', reports_views.reports_products, name='reports_products'),
    path('reports/financial/', reports_views.reports_financial, name='reports_financial'),

    # Печать документов
    path('orders/<int:order_id>/print/contract/', pdf_views.print_contract, name='print_contract'),
    path('orders/<int:order_id>/print/acceptance/', pdf_views.print_acceptance, name='print_acceptance'),
    path('orders/<int:order_id>/print/return/', pdf_views.print_return, name='print_return'),
    path('payments/<int:payment_id>/print/receipt/', pdf_views.print_receipt, name='print_receipt'),
    path('clients/<int:client_id>/payments/print/receipts/', pdf_views.print_receipts_bulk, name='print_receipts_bulk'),
    path('orders/<int:order_id>/notify/', views.send_overdue_notification, name='send_notification'),

    # Управление пользователями
    path('users/', views.users_management, name='users_management'),
    path('users/<int:user_id>/toggle/', views.toggle_user_active, name='toggle_user_active'),
    path('users/<int:user_id>/assign-group/', views.assign_user_group, name='assign_user_group'),
    path('users/<int:user_id>/remove-group/<int:group_id>/', views.remove_user_group, name='remove_user_group'),
    
    # Матрица прав
    path('permissions/', views.permissions_matrix, name='permissions_matrix'),

    # API
    path('api/overdue-orders/', views.api_overdue_orders, name='api_overdue_orders'),

    # Бэкапы
    path('backup/download/', views.download_latest_backup, name='download_backup'),
    path('backup/create/', views.create_backup_now, name='create_backup'),

    # Товары
    path('products/', inventory_views.products_list, name='products_list'),
    path('products/create/', inventory_views.create_product, name='create_product'),
    path('products/<int:product_id>/edit/', inventory_views.edit_product, name='edit_product'),
    path('products/<int:product_id>/report/', inventory_views.product_report, name='product_report'),

    # Склады
    path('warehouses/', inventory_views.warehouse_list, name='warehouse_list'),
    path('warehouses/create/', inventory_views.create_warehouse, name='create_warehouse'),
    path('warehouses/<int:warehouse_id>/delete/', inventory_views.delete_warehouse, name='delete_warehouse'),

    # Создатель — директора
    path('superadmin/directors/', views.creator_directors, name='creator_directors'),
    path('superadmin/directors/<int:user_id>/', views.creator_director_detail, name='creator_director_detail'),
    path('superadmin/directors/<int:user_id>/edit/', views.edit_director_settings, name='edit_director_settings'),

    # Создание сотрудника
    path('users/create-employee/', views.create_employee, name='create_employee'),

    # Смена пароля
    path('users/<int:user_id>/change-password/', views.change_user_password, name='change_user_password'),

    # Лог активности сотрудника
    path('users/<int:user_id>/activity/', views.employee_activity, name='employee_activity'),

    # Сообщения директора создателю
    path('messages/send/', views.send_message, name='send_message'),
    path('superadmin/messages/<int:msg_id>/read/', views.mark_message_read, name='mark_message_read'),

    # Массовые уведомления
    path('notifications/', views.broadcast_notifications, name='broadcast_notifications'),
]