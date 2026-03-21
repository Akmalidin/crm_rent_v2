from django.urls import path
from . import telegram_webhook_complete, views, reports_views, pdf_views, portal_views
from apps.clients import views as clients_views
from apps.inventory import views as inventory_views
from django.contrib.auth import views as auth_views

app_name = 'main'
urlpatterns = [
        # Авторизация
    path('offline/', views.offline_view, name='offline'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register_view, name='register'),
    path('pending-approval/', views.pending_approval, name='pending_approval'),
    path('superadmin/', views.superuser_panel, name='superuser_panel'),
    
    # Настройка компании
    path('setup-company/', views.setup_company, name='setup_company'),
    path('company/edit/', views.edit_company, name='edit_company'),


    # Главная
    path('', views.root_view, name='root'),
    path('dashboard/', views.dashboard, name='dashboard'),
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
    path('clients/<int:client_id>/reset-balance/', views.reset_client_balance, name='reset_client_balance'),
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
    path('reports/financial/pdf/', pdf_views.print_financial_report, name='print_financial_report'),
    path('clients/<int:client_id>/payments/print/receipts/', pdf_views.print_receipts_bulk, name='print_receipts_bulk'),
    path('clients/<int:client_id>/discounts/', clients_views.client_discounts, name='client_discounts'),
    path('api/discount/', clients_views.api_client_discount, name='api_client_discount'),
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

    # SSE уведомления
    path('sse/', views.sse_stream, name='sse_stream'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),

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

    # Аудит-лог
    path('audit/', views.audit_log, name='audit_log'),

    # Профиль
    path('profile/', views.my_profile, name='my_profile'),

    # Тикеты (обращения)
    path('messages/', views.ticket_list, name='ticket_list'),
    path('messages/send/', views.send_message, name='send_message'),
    path('messages/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    path('messages/<int:ticket_id>/edit/', views.edit_ticket, name='edit_ticket'),
    path('messages/<int:ticket_id>/reply/', views.add_reply, name='reply_ticket'),
    path('messages/<int:ticket_id>/close/', views.close_ticket, name='close_ticket'),
    path('superadmin/messages/<int:msg_id>/read/', views.mark_message_read, name='mark_message_read'),

    # Массовые уведомления
    path('notifications/', views.broadcast_notifications, name='broadcast_notifications'),

    # Расходы
    path('expenses/', views.expenses_list, name='expenses_list'),
    path('expenses/create/', views.create_expense, name='create_expense'),
    path('expenses/<int:expense_id>/delete/', views.delete_expense, name='delete_expense'),

    # Файлы к заказу
    path('orders/<int:order_id>/attachments/upload/', views.upload_order_attachment, name='upload_order_attachment'),
    path('attachments/<int:attachment_id>/delete/', views.delete_order_attachment, name='delete_order_attachment'),

    # Excel экспорт
    path('export/clients.xlsx', views.export_clients_xlsx, name='export_clients'),
    path('export/orders.xlsx', views.export_orders_xlsx, name='export_orders'),
    path('export/payments.xlsx', views.export_payments_xlsx, name='export_payments'),

    # Клиентский портал (публичный, по токену)
    path('portal/', portal_views.portal_login, name='portal_login'),
    path('portal/<uuid:token>/', portal_views.portal_catalog, name='portal_catalog'),
    path('portal/<uuid:token>/book/<int:product_id>/', portal_views.portal_book, name='portal_book'),
    path('portal/<uuid:token>/bookings/', portal_views.portal_my_bookings, name='portal_my_bookings'),
    path('portal/<uuid:token>/orders/', portal_views.portal_my_orders, name='portal_my_orders'),

    # Управление заявками (для персонала)
    path('bookings/', views.bookings_list, name='bookings_list'),
    path('bookings/<int:booking_id>/approve/', views.booking_approve, name='booking_approve'),
    path('bookings/<int:booking_id>/reject/', views.booking_reject, name='booking_reject'),

    # Отправить ссылку на портал клиенту
    path('clients/<int:client_id>/portal-link/', views.send_portal_link, name='send_portal_link'),

    # === Скрытый аудит-центр (только суперюзер) ===
    path('xsec-audit/', views.xsec_audit, name='xsec_audit'),
    path('xsec-audit/backup/create/', views.xsec_backup_create, name='xsec_backup_create'),
    path('xsec-audit/backup/<str:backup_name>/restore/', views.xsec_backup_restore, name='xsec_backup_restore'),
    path('xsec-audit/backup/<str:backup_name>/download/', views.xsec_backup_download, name='xsec_backup_download'),
    path('xsec-audit/backup/<str:backup_name>/delete/', views.xsec_backup_delete, name='xsec_backup_delete'),
    path('xsec-beacon/', views.xsec_beacon, name='xsec_beacon'),
]