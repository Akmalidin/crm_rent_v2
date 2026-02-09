# apps/main/reports_views.py
# -*- coding: utf-8 -*-
"""
Views для отчётов
"""
from django.shortcuts import render
from django.db.models import Sum, Count, Q, F
from apps.clients.models import Client
from apps.rental.models import RentalOrder, OrderItem, Payment
from apps.inventory.models import Product
from datetime import datetime, timedelta
from django.utils import timezone
from collections import defaultdict
import calendar


def reports_main(request):
    """Главная страница отчётов"""
    return render(request, 'reports/main.html')


def reports_monthly(request):
    """Отчёт по месяцам"""
    
    # Получаем данные за последние 12 месяцев
    today = timezone.now()
    months_data = []
    
    for i in range(11, -1, -1):
        # Вычисляем месяц
        month_date = today - timedelta(days=30*i)
        start_date = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Конец месяца
        last_day = calendar.monthrange(start_date.year, start_date.month)[1]
        end_date = start_date.replace(day=last_day, hour=23, minute=59, second=59)
        
        # Заказы за месяц
        orders = RentalOrder.objects.filter(created_at__range=[start_date, end_date])
        orders_count = orders.count()
        
        # Доход за месяц (сумма всех заказов)
        total_income = 0
        for order in orders:
            total_income += order.get_current_total()
        
        # Оплаты за месяц
        payments = Payment.objects.filter(payment_date__range=[start_date, end_date])
        total_paid = payments.aggregate(total=Sum('amount'))['total'] or 0
        
        # Новые клиенты
        new_clients = Client.objects.filter(created_at__range=[start_date, end_date]).count()
        
        months_data.append({
            'month': start_date.strftime('%B %Y'),
            'month_short': start_date.strftime('%b'),
            'orders_count': orders_count,
            'total_income': int(total_income),
            'total_paid': int(total_paid),
            'new_clients': new_clients,
        })
    
    context = {
        'months_data': months_data,
    }
    
    return render(request, 'reports/monthly.html', context)


def reports_clients(request):
    """Отчёт по клиентам"""
    
    # Все клиенты с расчётами
    clients_data = []
    
    for client in Client.objects.all():
        total_orders = client.rental_orders.count()
        active_orders = client.rental_orders.filter(status='open').count()
        
        # Всего потрачено (сумма всех заказов)
        total_spent = 0
        for order in client.rental_orders.all():
            total_spent += order.get_current_total()
        
        # Всего оплачено
        total_paid = client.get_total_paid()
        
        # Баланс
        balance = client.get_wallet_balance()
        
        clients_data.append({
            'client': client,
            'total_orders': total_orders,
            'active_orders': active_orders,
            'total_spent': int(total_spent),
            'total_paid': int(total_paid),
            'balance': int(balance),
        })
    
    # Сортировка по общей сумме (топ клиенты)
    clients_data_sorted = sorted(clients_data, key=lambda x: x['total_spent'], reverse=True)
    
    # Топ должники
    debtors = [c for c in clients_data if c['balance'] < 0]
    debtors_sorted = sorted(debtors, key=lambda x: x['balance'])
    
    context = {
        'clients_data': clients_data_sorted,
        'top_clients': clients_data_sorted[:10],
        'top_debtors': debtors_sorted[:10],
        'total_clients': len(clients_data),
        'clients_with_debt': len(debtors),
    }
    
    return render(request, 'reports/clients.html', context)


def reports_products(request):
    """Отчёт по товарам"""
    
    products_data = []
    
    for product in Product.objects.all():
        # Сколько раз брали
        times_rented = OrderItem.objects.filter(product=product).count()
        
        # Общее количество взятое
        total_quantity = OrderItem.objects.filter(product=product).aggregate(
            total=Sum('quantity_taken')
        )['total'] or 0
        
        # Общий доход
        total_income = OrderItem.objects.filter(product=product).aggregate(
            total=Sum('current_total_cost')
        )['total'] or 0
        
        # В аренде сейчас
        in_rent = OrderItem.objects.filter(
            product=product,
            quantity_remaining__gt=0
        ).aggregate(total=Sum('quantity_remaining'))['total'] or 0
        
        products_data.append({
            'product': product,
            'times_rented': times_rented,
            'total_quantity': total_quantity,
            'total_income': int(total_income),
            'in_rent': in_rent,
            'available': product.quantity_available,
        })
    
    # Сортировка по доходу
    products_by_income = sorted(products_data, key=lambda x: x['total_income'], reverse=True)
    
    # Сортировка по популярности
    products_by_popularity = sorted(products_data, key=lambda x: x['times_rented'], reverse=True)
    
    context = {
        'products_data': products_data,
        'top_by_income': products_by_income[:10],
        'top_by_popularity': products_by_popularity[:10],
    }
    
    return render(request, 'reports/products.html', context)


def reports_financial(request):
    """Финансовый отчёт"""
    
    # Общая статистика
    total_income = 0
    for order in RentalOrder.objects.all():
        total_income += order.get_current_total()
    
    total_paid = Payment.objects.aggregate(total=Sum('amount'))['total'] or 0
    
    total_debt = 0
    for client in Client.objects.all():
        total_debt += client.get_debt()
    
    # Оплаты по месяцам (последние 6)
    today = timezone.now()
    payments_monthly = []
    
    for i in range(5, -1, -1):
        month_date = today - timedelta(days=30*i)
        start_date = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(start_date.year, start_date.month)[1]
        end_date = start_date.replace(day=last_day, hour=23, minute=59, second=59)
        
        payments = Payment.objects.filter(payment_date__range=[start_date, end_date])
        total = payments.aggregate(total=Sum('amount'))['total'] or 0
        
        payments_monthly.append({
            'month': start_date.strftime('%B'),
            'total': int(total),
        })
    
    # Последние оплаты
    recent_payments = Payment.objects.select_related('client').order_by('-payment_date')[:20]
    
    context = {
        'total_income': int(total_income),
        'total_paid': int(total_paid),
        'total_debt': int(total_debt),
        'payments_monthly': payments_monthly,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'reports/financial.html', context)