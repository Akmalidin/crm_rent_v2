# apps/main/reports_views.py
# -*- coding: utf-8 -*-
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from apps.clients.models import Client
from apps.rental.models import RentalOrder, OrderItem, Payment
from apps.inventory.models import Product
from datetime import timedelta
from django.utils import timezone
import calendar


def _get_owner(request):
    from apps.main.views import get_tenant_owner
    return get_tenant_owner(request.user)


@login_required
def reports_main(request):
    return render(request, 'reports/main.html')


@login_required
def reports_monthly(request):
    owner = _get_owner(request)
    today = timezone.now()
    months_data = []

    for i in range(11, -1, -1):
        month_date = today - timedelta(days=30*i)
        start_date = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(start_date.year, start_date.month)[1]
        end_date = start_date.replace(day=last_day, hour=23, minute=59, second=59)

        orders = RentalOrder.objects.filter(client__owner=owner, created_at__range=[start_date, end_date])
        orders_count = orders.count()
        total_income = sum(o.get_current_total() for o in orders)

        total_paid = Payment.objects.filter(
            client__owner=owner, payment_date__range=[start_date, end_date]
        ).aggregate(total=Sum('amount'))['total'] or 0

        new_clients = Client.objects.filter(owner=owner, created_at__range=[start_date, end_date]).count()

        months_data.append({
            'month': start_date.strftime('%B %Y'),
            'month_short': start_date.strftime('%b'),
            'orders_count': orders_count,
            'total_income': int(total_income),
            'total_paid': int(total_paid),
            'new_clients': new_clients,
        })

    return render(request, 'reports/monthly.html', {'months_data': months_data})


@login_required
def reports_clients(request):
    owner = _get_owner(request)
    clients_data = []

    for client in Client.objects.filter(owner=owner):
        total_spent = sum(o.get_current_total() for o in client.rental_orders.all())
        clients_data.append({
            'client': client,
            'total_orders': client.rental_orders.count(),
            'active_orders': client.rental_orders.filter(status='open').count(),
            'total_spent': int(total_spent),
            'total_paid': int(client.get_total_paid()),
            'balance': int(client.get_wallet_balance()),
        })

    clients_data_sorted = sorted(clients_data, key=lambda x: x['total_spent'], reverse=True)
    debtors = sorted([c for c in clients_data if c['balance'] < 0], key=lambda x: x['balance'])

    return render(request, 'reports/clients.html', {
        'clients_data': clients_data_sorted,
        'top_clients': clients_data_sorted[:10],
        'top_debtors': debtors[:10],
        'total_clients': len(clients_data),
        'clients_with_debt': len(debtors),
    })


@login_required
def reports_products(request):
    owner = _get_owner(request)
    products_data = []

    for product in Product.objects.filter(owner=owner):
        qs = OrderItem.objects.filter(product=product, order__client__owner=owner)
        products_data.append({
            'product': product,
            'times_rented': qs.count(),
            'total_quantity': qs.aggregate(t=Sum('quantity_taken'))['t'] or 0,
            'total_income': int(qs.aggregate(t=Sum('current_total_cost'))['t'] or 0),
            'in_rent': qs.filter(quantity_remaining__gt=0).aggregate(t=Sum('quantity_remaining'))['t'] or 0,
            'available': product.quantity_available,
        })

    return render(request, 'reports/products.html', {
        'products_data': products_data,
        'top_by_income': sorted(products_data, key=lambda x: x['total_income'], reverse=True)[:10],
        'top_by_popularity': sorted(products_data, key=lambda x: x['times_rented'], reverse=True)[:10],
    })


@login_required
def reports_financial(request):
    from apps.main.models import Expense
    owner = _get_owner(request)

    total_income = sum(o.get_current_total() for o in RentalOrder.objects.filter(client__owner=owner))
    total_paid = Payment.objects.filter(client__owner=owner).aggregate(t=Sum('amount'))['t'] or 0
    total_debt = sum(c.get_debt() for c in Client.objects.filter(owner=owner))
    total_expenses = Expense.objects.filter(owner=owner).aggregate(t=Sum('amount'))['t'] or 0
    net_profit = int(total_paid) - int(total_expenses)

    today = timezone.now()
    payments_monthly = []
    for i in range(5, -1, -1):
        month_date = today - timedelta(days=30*i)
        start_date = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(start_date.year, start_date.month)[1]
        end_date = start_date.replace(day=last_day, hour=23, minute=59, second=59)
        paid = Payment.objects.filter(
            client__owner=owner, payment_date__range=[start_date, end_date]
        ).aggregate(t=Sum('amount'))['t'] or 0
        expenses = Expense.objects.filter(
            owner=owner, date__range=[start_date, end_date]
        ).aggregate(t=Sum('amount'))['t'] or 0
        payments_monthly.append({
            'month': start_date.strftime('%B'),
            'total': int(paid),
            'expenses': int(expenses),
            'net': int(paid) - int(expenses),
        })

    recent_payments = Payment.objects.filter(client__owner=owner).select_related('client').order_by('-payment_date')[:20]

    return render(request, 'reports/financial.html', {
        'total_income': int(total_income),
        'total_paid': int(total_paid),
        'total_debt': int(total_debt),
        'total_expenses': int(total_expenses),
        'net_profit': net_profit,
        'payments_monthly': payments_monthly,
        'recent_payments': recent_payments,
    })
