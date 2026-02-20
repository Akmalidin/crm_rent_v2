from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count, Q
from apps.clients.models import Client
from apps.rental.models import RentalOrder, OrderItem, Payment, ReturnDocument, Product
from apps.inventory.models import Product, Category
from datetime import datetime, timedelta
from django.utils import timezone
import json
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
@login_required
def dashboard(request):
    """Современный дашборд с графиками"""
    
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # === СТАТИСТИКА ===
    total_clients = Client.objects.count()
    new_clients_week = Client.objects.filter(created_at__gte=week_ago).count()
    
    active_orders = RentalOrder.objects.filter(status='open').count()
    total_orders = RentalOrder.objects.count()
    
    # Общий долг и должники
    all_clients = Client.objects.all()
    total_debt = sum(float(c.get_total_debt()) for c in all_clients)
    debtors_count = sum(1 for c in all_clients if float(c.get_wallet_balance()) < 0)
    
    # Доход за месяц
    revenue_month = Payment.objects.filter(
        payment_date__gte=month_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Рост дохода (примерно)
    prev_month = month_ago - timedelta(days=30)
    revenue_prev_month = Payment.objects.filter(
        payment_date__gte=prev_month,
        payment_date__lt=month_ago
    ).aggregate(total=Sum('amount'))['total'] or 1
    revenue_growth = int(((revenue_month - revenue_prev_month) / revenue_prev_month) * 100) if revenue_prev_month > 0 else 0
    
    # === ГРАФИК ДОХОДОВ ПО ДНЯМ ===
    revenue_labels = []
    revenue_data = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        revenue_labels.append(day.strftime('%d.%m'))
        day_revenue = Payment.objects.filter(
            payment_date__date=day.date()
        ).aggregate(total=Sum('amount'))['total'] or 0
        revenue_data.append(float(day_revenue))
    
    # === КРУГОВАЯ ДИАГРАММА ===
    total_paid = sum(float(c.get_total_paid()) for c in all_clients)
    total_credit = sum(float(c.get_wallet_balance()) for c in all_clients if float(c.get_wallet_balance()) > 0)
    
    # === ГРАФИК ЗАКАЗОВ ===
    orders_labels = []
    orders_open_data = []
    orders_closed_data = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        orders_labels.append(day.strftime('%d.%m'))
        
        open_count = RentalOrder.objects.filter(
            created_at__date=day.date(),
            status='open'
        ).count()
        closed_count = RentalOrder.objects.filter(
            created_at__date=day.date(),
            status='closed'
        ).count()
        
        orders_open_data.append(open_count)
        orders_closed_data.append(closed_count)
    
    # === ТОП-5 ТОВАРОВ ===
    products_stats = OrderItem.objects.values('product__name').annotate(
        rental_count=Count('id')
    ).order_by('-rental_count')[:5]
    
    max_count = products_stats[0]['rental_count'] if products_stats else 1
    top_products = [
        {
            'name': p['product__name'],
            'rental_count': p['rental_count'],
            'percentage': int((p['rental_count'] / max_count) * 100)
        }
        for p in products_stats
    ]
    
    # === ПРОСРОЧЕННЫЕ ЗАКАЗЫ ===
    overdue_orders = []
    for order in RentalOrder.objects.filter(status='open').prefetch_related('items__product', 'client'):
        overdue_items_list = [
            item for item in order.items.all()
            if item.quantity_remaining > 0 and item.planned_return_date < now
        ]
        if overdue_items_list:
            days_overdue = (now - min(item.planned_return_date for item in overdue_items_list)).days
            overdue_orders.append({
                'id': order.id,
                'client': order.client,
                'days_overdue': days_overdue,
                'overdue_items': len(overdue_items_list),
                'total': order.get_current_total(),
            })
    
    # Сортируем по дням просрочки
    overdue_orders.sort(key=lambda x: x['days_overdue'], reverse=True)
    
    context = {
        'now': now,
        # Статистика
        'total_clients': total_clients,
        'new_clients_week': new_clients_week,
        'active_orders': active_orders,
        'total_orders': total_orders,
        'total_debt': total_debt,
        'debtors_count': debtors_count,
        'revenue_month': revenue_month,
        'revenue_growth': revenue_growth,
        # График доходов
        'revenue_labels': json.dumps(revenue_labels),
        'revenue_data': json.dumps(revenue_data),
        # Круговая диаграмма
        'total_paid': total_paid,
        'total_credit': total_credit,
        # График заказов
        'orders_labels': json.dumps(orders_labels),
        'orders_open_data': json.dumps(orders_open_data),
        'orders_closed_data': json.dumps(orders_closed_data),
        # Топ товары
        'top_products': top_products,
        # Просроченные
        'overdue_orders': overdue_orders,
    }
    
    return render(request, 'main/dashboard.html', context)

@login_required
def clients_list(request):
    """Список клиентов с фильтрами"""
    from apps.clients.models import Client
    
    # Параметры фильтров
    filter_type  = request.GET.get('filter', '')      # debt / credit / active / all
    date_range   = request.GET.get('date_range', '')  # today / week / month
    amount_min   = request.GET.get('amount_min', '')
    amount_max   = request.GET.get('amount_max', '')
    sort_by      = request.GET.get('sort', '-created_at')
    
    # Базовый queryset
    clients = Client.objects.prefetch_related('phones', 'rental_orders')
    
    # === СОРТИРОВКА ===
    if sort_by == '-created_at':
        clients = clients.order_by('-created_at')
    elif sort_by == 'created_at':
        clients = clients.order_by('created_at')
    elif sort_by == 'name':
        clients = clients.order_by('last_name', 'first_name')
    else:
        clients = clients.order_by('-created_at')
    
    # === ФИЛЬТР ПО ДАТЕ РЕГИСТРАЦИИ ===
    now = timezone.now()
    if date_range == 'today':
        clients = clients.filter(created_at__date=now.date())
    elif date_range == 'week':
        clients = clients.filter(created_at__gte=now - timedelta(days=7))
    elif date_range == 'month':
        clients = clients.filter(created_at__gte=now - timedelta(days=30))
    
    # === ФИЛЬТР ПО ТИПУ (долг / аванс / активные) ===
    # Применяем post-filter (т.к. баланс вычисляется)
    if filter_type or amount_min or amount_max:
        filtered_ids = []
        for client in clients:
            balance = float(client.get_wallet_balance())
            debt = float(client.get_total_debt())
            
            # Фильтр по типу
            if filter_type == 'debt' and balance >= 0:
                continue
            if filter_type == 'credit' and balance <= 0:
                continue
            if filter_type == 'active':
                has_open = client.rental_orders.filter(status='open').exists()
                if not has_open:
                    continue
            
            # Фильтр по сумме долга
            if amount_min and debt < float(amount_min):
                continue
            if amount_max and debt > float(amount_max):
                continue
            
            filtered_ids.append(client.id)
        clients = clients.filter(id__in=filtered_ids)
    
    # Статистика
    all_clients = Client.objects.prefetch_related('phones', 'rental_orders')
    debt_count   = sum(1 for c in all_clients if float(c.get_wallet_balance()) < 0)
    credit_count = sum(1 for c in all_clients if float(c.get_wallet_balance()) > 0)
    active_count = sum(1 for c in all_clients if c.rental_orders.filter(status='open').exists())
    
    context = {
        'clients': clients,
        'total_clients': all_clients.count(),
        'debt_count': debt_count,
        'credit_count': credit_count,
        'active_count': active_count,
        # Текущие фильтры
        'current_filter': filter_type,
        'current_date_range': date_range,
        'current_amount_min': amount_min,
        'current_amount_max': amount_max,
        'current_sort': sort_by,
        'filters_active': any([filter_type, date_range, amount_min, amount_max]),
    }
    
    return render(request, 'clients/list.html', context)

@login_required
def client_detail(request, client_id):
    """Карточка клиента с группированной историей"""
    
    client = get_object_or_404(Client, id=client_id)
    
    # Активные заказы
    active_orders = client.rental_orders.filter(status='open').prefetch_related('items__product')
    
    # Все заказы
    all_orders = client.rental_orders.all().order_by('-created_at')
    
    # История оплат (последние 10 для старой секции, если нужна)
    payments = client.payments.all().order_by('-payment_date')[:10]
    
    # === ГРУППИРОВАННАЯ ИСТОРИЯ ПО ЗАКАЗАМ ===
    import re
    from apps.rental.models import ReturnDocument
    
    order_groups = []
    
    for order in client.rental_orders.all().order_by('-created_at'):
        # События внутри заказа
        order_events = []
        
        # 1. Создание заказа
        order_events.append({
            'type': 'order_created',
            'date': order.created_at,
            'description': 'Создан заказ',
            'items': list(order.items.all()),
            'total': float(order.get_original_total()),
        })
        
        # 2. Возвраты по этому заказу
        for order_item in order.items.all():
            for return_item in order_item.returns.all():
                order_events.append({
                    'type': 'return',
                    'date': return_item.return_document.return_date,
                    'description': 'Возврат товаров',
                    'return_item': return_item,
                })
        
        # 3. Оплаты для этого заказа
        for payment in client.payments.all():
            if payment.notes and f'#{order.id}' in payment.notes:
                payment_for_order = None
                if 'Распределение:' in payment.notes:
                    for line in payment.notes.split('\n'):
                        # Используем regex который игнорирует пробелы
                        pattern = rf'Заказ\s*#{order.id}\s*:\s*(\d+(?:[\.,]\d+)?)\s*сом'
                        match = re.search(pattern, line)
                        if match:
                            payment_for_order = float(match.group(1).replace(',', '.'))
                            break
                
                if payment_for_order:
                    order_events.append({
                        'type': 'payment',
                        'date': payment.payment_date,
                        'description': 'Оплата',
                        'amount': payment_for_order,
                        'payment_method': payment.get_payment_method_display(),
                        'is_partial': 'частично' in payment.notes.lower(),
                    })
        
        # Сортируем события по дате
        order_events.sort(key=lambda x: x['date'])
        
        # Считаем итоги по заказу
        total_paid_for_order = sum(e['amount'] for e in order_events if e['type'] == 'payment')
        current_order_cost = float(order.get_current_total())
        order_debt = current_order_cost - total_paid_for_order
        
        # Проверяем есть ли невозвращённые товары
        from django.utils import timezone
        now = timezone.now()

        has_unreturned = order.items.filter(
            quantity_remaining__gt=0
        ).exists()

        is_overdue = order.items.filter(
            quantity_remaining__gt=0,
            planned_return_date__lt=now
        ).exists()
        
        order_groups.append({
            'order': order,
            'events': order_events,
            'total_paid': total_paid_for_order,
            'current_cost': current_order_cost,
            'debt': order_debt,
            'has_unreturned_items': has_unreturned,
            'is_overdue': is_overdue,
        })
    
    context = {
        'client': client,
        'balance': client.get_wallet_balance(),
        'debt': client.get_debt(),
        'credit': client.get_credit(),
        'total_paid': client.get_total_paid(),
        'total_debt': client.get_total_debt(),
        'active_orders': active_orders,
        'all_orders': all_orders,
        'payments': payments,
        'order_groups': order_groups,
    }
    
    return render(request, 'clients/detail.html', context)

@login_required
@permission_required('rental.add_rentalorder', raise_exception=True)
def create_order(request):
    """Создание заказа"""
    
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        notes = request.POST.get('notes', '')
        
        client = get_object_or_404(Client, id=client_id)
        
        # Создаём заказ
        order = RentalOrder.objects.create(
            client=client,
            notes=notes,
            status='open'
        )
        
        # Добавляем товары
        items_count = 0
        for key in request.POST:
            if key.startswith('items[') and key.endswith('[product_id]'):
                # Извлекаем индекс
                import re
                match = re.search(r'items\[(\d+)\]', key)
                if match:
                    index = match.group(1)
                    
                    product_id = request.POST.get(f'items[{index}][product_id]')
                    quantity = int(request.POST.get(f'items[{index}][quantity]', 0))
                    days = int(request.POST.get(f'items[{index}][days]', 0))
                    hours = int(request.POST.get(f'items[{index}][hours]', 0))
                    
                    if product_id and quantity > 0:
                        product = get_object_or_404(Product, id=product_id)
                        
                        # Проверяем доступность
                        if product.quantity_available >= quantity:
                            # Создаём OrderItem
                            OrderItem.objects.create(
                                order=order,
                                product=product,
                                quantity_taken=quantity,
                                quantity_remaining=quantity,
                                issued_date=timezone.now(),
                                planned_return_date=timezone.now() + timedelta(days=days, hours=hours),
                                rental_days=days,
                                rental_hours=hours,
                                price_per_day=product.price_per_day,
                                price_per_hour=product.price_per_hour
                            )
                            
                            # Уменьшаем доступное количество
                            product.quantity_available -= quantity
                            product.save()
                            
                            items_count += 1
        
        if items_count > 0:
            return redirect('main:client_detail', client_id=client.id)
        else:
            order.delete()
            return redirect('main:create_order')
    
    # GET запрос
    clients = Client.objects.all().order_by('last_name', 'first_name')
    products = Product.objects.filter(is_active=True, quantity_available__gt=0).order_by('name')
    
    context = {
        'clients': clients,
        'products': products,
    }
    
    return render(request, 'rental/create_order.html', context)

def orders_list(request):
    """Список всех заказов с фильтрами"""
    from apps.rental.models import RentalOrder
    from apps.clients.models import Client
    
    # Получаем параметры фильтров
    status        = request.GET.get('status', '')        # open / closed / all
    date_range    = request.GET.get('date_range', '')    # today / week / month / all
    overdue_only  = request.GET.get('overdue', '')       # 1 = только просроченные
    amount_min    = request.GET.get('amount_min', '')    # минимальная сумма
    amount_max    = request.GET.get('amount_max', '')    # максимальная сумма
    sort_by       = request.GET.get('sort', '-created_at')  # сортировка
    
    # Базовый queryset
    orders = RentalOrder.objects.select_related('client').prefetch_related('items')
    
    # === ФИЛЬТР ПО СТАТУСУ ===
    if status == 'open':
        orders = orders.filter(status='open')
    elif status == 'closed':
        orders = orders.filter(status='closed')
    
    # === ФИЛЬТР ПО ДАТЕ ===
    now = timezone.now()
    if date_range == 'today':
        orders = orders.filter(created_at__date=now.date())
    elif date_range == 'week':
        orders = orders.filter(created_at__gte=now - timedelta(days=7))
    elif date_range == 'month':
        orders = orders.filter(created_at__gte=now - timedelta(days=30))
    
    # === ФИЛЬТР ПРОСРОЧЕННЫХ ===
    if overdue_only == '1':
        overdue_ids = []
        for order in orders.filter(status='open'):
            for item in order.items.all():
                if item.quantity_remaining > 0 and item.planned_return_date < now:
                    overdue_ids.append(order.id)
                    break
        orders = orders.filter(id__in=overdue_ids)
    
    # === СОРТИРОВКА ===
    valid_sorts = ['-created_at', 'created_at', '-id', 'id']
    if sort_by in valid_sorts:
        orders = orders.order_by(sort_by)
    else:
        orders = orders.order_by('-created_at')
    
    # === ФИЛЬТР ПО СУММЕ (post-filter т.к. сумма вычисляется) ===
    if amount_min or amount_max:
        filtered = []
        for order in orders:
            total = float(order.get_current_total())
            if amount_min and total < float(amount_min):
                continue
            if amount_max and total > float(amount_max):
                continue
            filtered.append(order.id)
        orders = orders.filter(id__in=filtered)
    
    # Статистика
    total_open   = RentalOrder.objects.filter(status='open').count()
    total_closed = RentalOrder.objects.filter(status='closed').count()
    
    # Просроченные
    overdue_count = 0
    for order in RentalOrder.objects.filter(status='open').prefetch_related('items'):
        for item in order.items.all():
            if item.quantity_remaining > 0 and item.planned_return_date < now:
                overdue_count += 1
                break
    
    context = {
        'orders': orders,
        'total_open': total_open,
        'total_closed': total_closed,
        'overdue_count': overdue_count,
        # Текущие фильтры (для отображения в форме)
        'current_status': status,
        'current_date_range': date_range,
        'current_overdue': overdue_only,
        'current_amount_min': amount_min,
        'current_amount_max': amount_max,
        'current_sort': sort_by,
        # Флаг что фильтр активен
        'filters_active': any([status, date_range, overdue_only, amount_min, amount_max]),
    }
    
    return render(request, 'rental/orders_list.html', context)


@login_required
def accept_payment(request):
    """Принять оплату с отслеживанием заказов"""
    
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method', 'cash')
        notes = request.POST.get('notes', '')
        selected_orders = request.POST.getlist('selected_orders')
        
        try:
            client = get_object_or_404(Client, id=client_id)
            payment_amount = float(amount)
            
            if payment_amount <= 0:
                return redirect('main:accept_payment')
            
            # Определяем заказы для оплаты
            if selected_orders:
                orders_to_pay = RentalOrder.objects.filter(
                    id__in=selected_orders,
                    client=client,
                    status='open'
                ).order_by('created_at')
            else:
                orders_to_pay = client.rental_orders.filter(status='open').order_by('created_at')
            
            # Распределяем оплату
            remaining_payment = payment_amount
            payment_distribution = []
            paid_orders = []
            
            for order in orders_to_pay:
                if remaining_payment <= 0:
                    break
                
                order_cost = float(order.get_current_total())
                
                if remaining_payment >= order_cost:
                    # Полностью оплачен
                    paid_amount = order_cost
                    remaining_payment -= order_cost
                    payment_distribution.append(f'Заказ #{order.id}: {paid_amount:.0f} сом (полностью)')
                    paid_orders.append(str(order.id))
                else:
                    # Частично оплачен
                    paid_amount = remaining_payment
                    payment_distribution.append(f'Заказ #{order.id}: {paid_amount:.0f} сом (частично)')
                    paid_orders.append(str(order.id))
                    remaining_payment = 0
            
            # Формируем примечание
            if paid_orders:
                order_note = f"Оплата для заказ{'ов' if len(paid_orders) > 1 else 'а'} #{', #'.join(paid_orders)}"
                if notes:
                    full_notes = f"{order_note}\n{notes}\n\nРаспределение:\n" + '\n'.join(payment_distribution)
                else:
                    full_notes = f"{order_note}\n\nРаспределение:\n" + '\n'.join(payment_distribution)
            else:
                full_notes = notes if notes else 'Аванс (нет открытых заказов)'
            
            # Создаём оплату
            Payment.objects.create(
                client=client,
                amount=payment_amount,
                payment_method=payment_method,
                notes=full_notes
            )
            
            return redirect('main:client_detail', client_id=client.id)
            
        except (ValueError, TypeError):
            return redirect('main:accept_payment')
    
    # GET запрос
    clients = Client.objects.all().order_by('last_name', 'first_name')
    
    # Клиенты с долгом
    clients_with_debt = []
    for client in clients:
        debt = client.get_debt()
        if debt > 0:
            open_orders = client.rental_orders.filter(status='open').order_by('created_at')
            orders_list = []
            for order in open_orders:
                orders_list.append({
                    'id': order.id,
                    'created_at': order.created_at,
                    'total': float(order.get_current_total()),
                    'items_count': order.items.count(),
                })
            
            clients_with_debt.append({
                'client': client,
                'debt': debt,
                'orders': orders_list,
            })
    
    # Выбранный клиент
    selected_client_id = request.GET.get('client')
    selected_client = None
    selected_client_orders = []
    
    if selected_client_id:
        try:
            selected_client = Client.objects.get(id=selected_client_id)
            for order in selected_client.rental_orders.filter(status='open').order_by('created_at'):
                selected_client_orders.append({
                    'id': order.id,
                    'created_at': order.created_at,
                    'total': float(order.get_current_total()),
                    'items_count': order.items.count(),
                })
        except Client.DoesNotExist:
            pass
    
    context = {
        'clients': clients,
        'clients_with_debt': clients_with_debt,
        'selected_client': selected_client,
        'selected_client_id': selected_client_id,
        'selected_client_orders': selected_client_orders,
    }
    
    return render(request, 'rental/payment.html', context)

@login_required
def returns_page(request):
    """Страница возвратов с предложением оплаты"""
    
    if request.method == 'POST':
        from apps.rental.models import ReturnDocument, ReturnItem
        
        client_id = request.POST.get('client_id')
        notes = request.POST.get('notes', '')
        payment_amount = request.POST.get('payment_amount', '0')
        
        # Создаём документ возврата
        return_doc = ReturnDocument.objects.create(notes=notes)
        
        # Обрабатываем возвраты
        has_returns = False
        total_cost = 0
        
        for key in request.POST:
            if key.startswith('return_') and request.POST[key]:
                item_id = key.replace('return_', '')
                quantity = int(request.POST[key])
                
                if quantity > 0:
                    try:
                        order_item = OrderItem.objects.get(id=item_id)
                        
                        if quantity <= order_item.quantity_remaining:
                            return_item = ReturnItem.objects.create(
                                return_document=return_doc,
                                order_item=order_item,
                                quantity=quantity
                            )
                            has_returns = True
                            total_cost += float(return_item.calculated_cost)
                    except OrderItem.DoesNotExist:
                        pass
        
        if has_returns:
            # Если клиент оплатил
            try:
                payment_amount = float(payment_amount)
                if payment_amount > 0:
                    Payment.objects.create(
                        client_id=client_id,
                        amount=payment_amount,
                        payment_method='cash',
                        notes=f'Оплата при возврате (Возврат #{return_doc.id})'
                    )
            except (ValueError, TypeError):
                pass
            
            return redirect('main:client_detail', client_id=client_id)
        else:
            return_doc.delete()
            return redirect(f'/rental/returns/?client_id={client_id}')
    
    # GET запрос
    clients_with_orders = []
    
    for client in Client.objects.all():
        active_orders = client.rental_orders.filter(status='open')
        if active_orders.exists():
            has_items = False
            for order in active_orders:
                if order.items.filter(quantity_remaining__gt=0).exists():
                    has_items = True
                    break
            
            if has_items:
                clients_with_orders.append({
                    'id': client.id,
                    'get_full_name': client.get_full_name(),
                    'active_count': active_orders.count(),
                    'balance': int(client.get_wallet_balance()),
                })
    
    # Если выбран клиент
    client_id = request.GET.get('client_id')
    selected_orders = []
    selected_client = None
    
    if client_id:
        try:
            selected_client = Client.objects.get(id=client_id)
            for order in selected_client.rental_orders.filter(status='open'):
                items_data = []
                for item in order.items.filter(quantity_remaining__gt=0):
                    items_data.append({
                        'id': item.id,
                        'product_name': item.product.name,
                        'quantity_taken': item.quantity_taken,
                        'quantity_returned': item.quantity_returned,
                        'quantity_remaining': item.quantity_remaining,
                        'issued_date': item.issued_date.strftime('%d.%m.%Y %H:%M'),
                        'planned_return_date': item.planned_return_date.strftime('%d.%m.%Y %H:%M'),
                        'current_total_cost': float(item.current_total_cost),
                    })
                
                if items_data:
                    selected_orders.append({
                        'id': order.id,
                        'created_at': order.created_at.strftime('%d.%m.%Y %H:%M'),
                        'total': float(order.get_current_total()),
                        'items': items_data,
                    })
        except Client.DoesNotExist:
            pass
    
    context = {
        'clients_with_orders': clients_with_orders,
        'selected_orders': selected_orders,
        'selected_client_id': client_id,
        'selected_client': selected_client,
    }
    
    return render(request, 'rental/returns.html', context)

@login_required
def history(request):
    """История операций сгруппированная по заказам"""
    
    selected_client_id = request.GET.get('client_id', '')
    
    # Список всех клиентов
    clients = Client.objects.all().order_by('last_name', 'first_name')
    
    # Если клиент не выбран
    if not selected_client_id:
        context = {
            'clients': clients,
            'selected_client': None,
            'order_groups': [],
        }
        return render(request, 'main/history.html', context)
    
    # Получаем клиента
    try:
        selected_client = Client.objects.get(id=selected_client_id)
    except Client.DoesNotExist:
        return redirect('main:history')
    
    # Группируем события по заказам
    import re
    from apps.rental.models import ReturnDocument
    
    order_groups = []
    
    for order in selected_client.rental_orders.all().order_by('-created_at'):
        # События внутри заказа
        order_events = []
        
        # 1. Создание заказа
        order_events.append({
            'type': 'order_created',
            'date': order.created_at,
            'description': 'Создан заказ',
            'items': list(order.items.all()),
            'total': float(order.get_original_total()),
        })
        
        # 2. Возвраты по этому заказу
        for order_item in order.items.all():
            for return_item in order_item.returns.all():
                order_events.append({
                    'type': 'return',
                    'date': return_item.return_document.return_date,
                    'description': 'Возврат товаров',
                    'return_item': return_item,
                })
        
        # 3. Оплаты для этого заказа
        for payment in selected_client.payments.all():
            if payment.notes and f'#{order.id}' in payment.notes:
                # Извлекаем сумму для этого заказа
                payment_for_order = None
                if 'Распределение:' in payment.notes:
                    for line in payment.notes.split('\n'):
                        if f'Заказ #{order.id}:' in line:
                            match = re.search(r'(\d+(?:\.\d+)?)\s*сом', line)
                            if match:
                                payment_for_order = float(match.group(1))
                                break
                
                if payment_for_order:
                    order_events.append({
                        'type': 'payment',
                        'date': payment.payment_date,
                        'description': 'Оплата',
                        'amount': payment_for_order,
                        'payment_method': payment.get_payment_method_display(),
                        'is_partial': 'частично' in payment.notes.lower(),
                    })
        
        # Сортируем события по дате
        order_events.sort(key=lambda x: x['date'])
        
        # Считаем итоги по заказу
        total_paid_for_order = sum(e['amount'] for e in order_events if e['type'] == 'payment')
        current_order_cost = float(order.get_current_total())
        order_debt = current_order_cost - total_paid_for_order
        
        # Проверяем есть ли невозвращённые товары
        from django.utils import timezone
        now = timezone.now()

        has_unreturned = order.items.filter(
            quantity_remaining__gt=0
        ).exists()

        is_overdue = order.items.filter(
            quantity_remaining__gt=0,
            planned_return_date__lt=now
        ).exists()
        
        order_groups.append({
            'order': order,
            'events': order_events,
            'total_paid': total_paid_for_order,
            'current_cost': current_order_cost,
            'debt': order_debt,
            'has_unreturned_items': has_unreturned,
            'is_overdue': is_overdue,
        })
    
    # Баланс клиента
    wallet_balance = selected_client.get_wallet_balance()
    total_paid = selected_client.get_total_paid()
    total_debt = selected_client.get_total_debt()
    
    context = {
        'clients': clients,
        'selected_client': selected_client,
        'selected_client_id': selected_client_id,
        'order_groups': order_groups,
        'wallet_balance': wallet_balance,
        'total_paid': total_paid,
        'total_debt': total_debt,
    }
    
    return render(request, 'main/history.html', context)

@login_required
def edit_order(request, order_id):
    """Редактирование заказа"""
    
    order = get_object_or_404(RentalOrder, id=order_id)
    
    # Только открытые заказы можно редактировать
    if order.status != 'open':
        return redirect('main:client_detail', client_id=order.client.id)
    
    if request.method == 'POST':
        from decimal import Decimal
        from datetime import timedelta
        
        # === ДОБАВЛЕНИЕ НОВОГО ТОВАРА ===
        if 'add_product' in request.POST:
            product_id = request.POST.get('new_product_id')
            quantity = int(request.POST.get('new_quantity', 0))
            days = int(request.POST.get('new_days', 0))
            hours = int(request.POST.get('new_hours', 0))
            
            if product_id and quantity > 0 and (days > 0 or hours > 0):
                try:
                    product = Product.objects.get(id=product_id)
                    
                    # Проверяем доступность
                    if product.quantity_available >= quantity:
                        # Уменьшаем доступное количество
                        product.quantity_available -= quantity
                        product.save()
                        
                        # Создаём новый OrderItem
                        issued_date = order.created_at
                        planned_return_date = issued_date + timedelta(days=days, hours=hours)
                        
                        # Рассчитываем стоимость
                        total_rental_hours = (days * 24) + hours
                        total_days_decimal = Decimal(total_rental_hours) / Decimal(24)
                        total_cost = product.price_per_day * total_days_decimal * Decimal(quantity)
                        
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity_taken=quantity,
                            quantity_returned=0,
                            quantity_remaining=quantity,
                            rental_days=days,
                            rental_hours=hours,
                            price_per_day=product.price_per_day,
                            issued_date=issued_date,
                            planned_return_date=planned_return_date,
                            original_total_cost=total_cost,
                            current_total_cost=total_cost,
                        )
                        
                        return redirect('main:edit_order', order_id=order.id)
                except Product.DoesNotExist:
                    pass
        
        # === ОБНОВЛЕНИЕ ПРИМЕЧАНИЙ ===
        notes = request.POST.get('notes', '')
        order.notes = notes
        order.save()
        
        # === ОБНОВЛЕНИЕ ТОВАРОВ ===
        for key in request.POST:
            if key.startswith('item_quantity_'):
                item_id = key.replace('item_quantity_', '')
                new_quantity = int(request.POST.get(key, 0))
                
                try:
                    order_item = OrderItem.objects.get(id=item_id, order=order)
                    
                    if new_quantity >= order_item.quantity_returned:
                        old_quantity = order_item.quantity_taken
                        difference = new_quantity - old_quantity
                        
                        if difference > 0:
                            if order_item.product.quantity_available >= difference:
                                order_item.product.quantity_available -= difference
                                order_item.product.save()
                                
                                order_item.quantity_taken = new_quantity
                                order_item.quantity_remaining = new_quantity - order_item.quantity_returned
                                
                                # Пересчёт
                                total_rental_hours = (order_item.rental_days * 24) + order_item.rental_hours
                                total_days_decimal = Decimal(total_rental_hours) / Decimal(24)
                                order_item.original_total_cost = order_item.price_per_day * total_days_decimal * Decimal(new_quantity)
                                order_item.current_total_cost = order_item.original_total_cost
                                
                                order_item.save()
                        else:
                            order_item.product.quantity_available += abs(difference)
                            order_item.product.save()
                            
                            order_item.quantity_taken = new_quantity
                            order_item.quantity_remaining = new_quantity - order_item.quantity_returned
                            
                            # Пересчёт
                            total_rental_hours = (order_item.rental_days * 24) + order_item.rental_hours
                            total_days_decimal = Decimal(total_rental_hours) / Decimal(24)
                            order_item.original_total_cost = order_item.price_per_day * total_days_decimal * Decimal(new_quantity)
                            order_item.current_total_cost = order_item.original_total_cost
                            
                            order_item.save()
                
                except OrderItem.DoesNotExist:
                    pass
            
            # Обновление дней
            if key.startswith('item_days_'):
                item_id = key.replace('item_days_', '')
                new_days = int(request.POST.get(key, 0))
                
                try:
                    order_item = OrderItem.objects.get(id=item_id, order=order)
                    order_item.rental_days = new_days
                    order_item.planned_return_date = order_item.issued_date + timedelta(days=new_days, hours=order_item.rental_hours)
                    
                    # Пересчёт
                    total_rental_hours = (new_days * 24) + order_item.rental_hours
                    total_days_decimal = Decimal(total_rental_hours) / Decimal(24)
                    order_item.original_total_cost = order_item.price_per_day * total_days_decimal * Decimal(order_item.quantity_taken)
                    order_item.current_total_cost = order_item.original_total_cost
                    
                    order_item.save()
                except OrderItem.DoesNotExist:
                    pass
            
            # Обновление часов
            if key.startswith('item_hours_'):
                item_id = key.replace('item_hours_', '')
                new_hours = int(request.POST.get(key, 0))
                
                try:
                    order_item = OrderItem.objects.get(id=item_id, order=order)
                    order_item.rental_hours = new_hours
                    order_item.planned_return_date = order_item.issued_date + timedelta(days=order_item.rental_days, hours=new_hours)
                    
                    # Пересчёт
                    total_rental_hours = (order_item.rental_days * 24) + new_hours
                    total_days_decimal = Decimal(total_rental_hours) / Decimal(24)
                    order_item.original_total_cost = order_item.price_per_day * total_days_decimal * Decimal(order_item.quantity_taken)
                    order_item.current_total_cost = order_item.original_total_cost
                    
                    order_item.save()
                except OrderItem.DoesNotExist:
                    pass
        
        # === УДАЛЕНИЕ ТОВАРОВ ===
        for key in request.POST:
            if key.startswith('delete_item_'):
                item_id = key.replace('delete_item_', '')
                
                try:
                    order_item = OrderItem.objects.get(id=item_id, order=order)
                    
                    if order_item.quantity_returned == 0:
                        order_item.product.quantity_available += order_item.quantity_taken
                        order_item.product.save()
                        order_item.delete()
                
                except OrderItem.DoesNotExist:
                    pass
        
        return redirect('main:client_detail', client_id=order.client.id)
    
    # GET запрос
    available_products = Product.objects.filter(is_active=True, quantity_available__gt=0).order_by('name')
    
    context = {
        'order': order,
        'available_products': available_products,
    }
    
    return render(request, 'rental/edit_order.html', context)

@login_required
def apply_credit_to_order(request, order_id):
    """Зачесть аванс клиента в счёт заказа"""
    
    order = get_object_or_404(RentalOrder, id=order_id)
    client = order.client
    
    # Получаем баланс клиента
    credit = client.get_credit()  # Переплата (аванс)
    
    if credit <= 0:
        # Нет аванса для зачёта
        return redirect('main:client_detail', client_id=client.id)
    
    # Получаем долг по заказу
    order_cost = float(order.get_current_total())
    
    # Считаем сколько уже оплачено по этому заказу
    paid_for_order = 0
    for payment in client.payments.all():
        if payment.notes and f'#{order.id}' in payment.notes:
            import re
            for line in payment.notes.split('\n'):
                if f'Заказ #{order.id}:' in line:
                    match = re.search(r'(\d+(?:\.\d+)?)\s*сом', line)
                    if match:
                        paid_for_order += float(match.group(1))
    
    order_debt = order_cost - paid_for_order
    
    if order_debt <= 0:
        # Заказ уже полностью оплачен
        return redirect('main:client_detail', client_id=client.id)
    
    # Зачитываем аванс
    from decimal import Decimal
    
    if credit >= order_debt:
        # Аванса хватает полностью покрыть долг
        amount_to_apply = Decimal(str(order_debt))
    else:
        # Аванса не хватает, зачитываем весь аванс
        amount_to_apply = Decimal(str(credit))
    
    # Создаём оплату как зачёт аванса
    Payment.objects.create(
        client=client,
        amount=amount_to_apply,
        payment_method='credit',  # Зачёт аванса
        notes=f'Зачёт аванса в счёт заказа\n\nРаспределение:\nЗаказ #{order.id}: {amount_to_apply:.0f} сом ({"полностью" if amount_to_apply >= order_debt else "частично"})'
    )
    
    return redirect('main:client_detail', client_id=client.id)

@login_required
def close_order(request, order_id):
    """Закрыть заказ вручную - все товары возвращаются на склад"""
    from apps.rental.models import ReturnDocument, ReturnItem
    from django.utils import timezone
    from decimal import Decimal
    
    order = get_object_or_404(RentalOrder, id=order_id)
    
    if order.status != 'open':
        return redirect('main:client_detail', client_id=order.client.id)
    
    now = timezone.now()
    
    # Создаём документ возврата для всех невозвращённых товаров
    items_to_return = list(order.items.filter(quantity_remaining__gt=0))
    
    if items_to_return:
        return_doc = ReturnDocument.objects.create(
            notes=f'Автоматический возврат при закрытии заказа #{order.id}',
            return_date=now
        )
        
        for item in items_to_return:
            # Рассчитываем фактическое время аренды
            delta = now - item.issued_date
            total_seconds = delta.total_seconds()
            actual_days = int(total_seconds // 86400)
            remaining_seconds = total_seconds % 86400
            actual_hours = int(remaining_seconds // 3600)
            
            # Рассчитываем стоимость
            calculated_cost = Decimal(item.quantity_remaining) * (
                Decimal(str(item.price_per_day)) * actual_days + 
                Decimal(str(item.price_per_hour)) * actual_hours
            )
            
            ReturnItem.objects.create(
                return_document=return_doc,
                order_item=item,
                quantity=item.quantity_remaining,
                actual_days=actual_days,
                actual_hours=actual_hours,
                calculated_cost=calculated_cost
            )
            
            # Обновляем остатки в OrderItem
            item.quantity_returned += item.quantity_remaining
            item.quantity_remaining = 0
            item.actual_cost = calculated_cost
            item.save()
            
            # Возвращаем товар на склад
            product = item.product
            product.quantity_available += item.quantity_taken
            product.save()
    
    # Закрываем заказ
    order.status = 'closed'
    order.save()
    
    messages.success(request, f'Заказ #{order.id} закрыт. Все товары возвращены на склад.')
    
    return redirect('main:client_detail', client_id=order.client.id)
from django.http import JsonResponse
from django.db.models import Q

def global_search(request):
    """Живой глобальный поиск - возвращает JSON"""
    
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': [], 'query': query})
    
    results = []
    
    # ==========================================
    # 1. ПОИСК КЛИЕНТОВ (по имени и телефону)
    # ==========================================
    from apps.clients.models import Client
    
    clients = Client.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(middle_name__icontains=query) |
        Q(phones__phone_number__icontains=query)
    ).distinct()[:5]
    
    for client in clients:
        # Получаем баланс
        balance = client.get_wallet_balance()
        balance_text = f'+{int(balance):,} сом'.replace(',', ' ') if balance > 0 else f'{int(balance):,} сом'.replace(',', ' ')
        
        # Основной телефон
        phone = client.phones.filter(is_primary=True).first()
        phone_text = phone.phone_number if phone else '—'
        
        results.append({
            'type': 'client',
            'icon': '👤',
            'title': client.get_full_name(),
            'subtitle': f'Тел: {phone_text}',
            'badge': balance_text,
            'badge_color': 'green' if balance >= 0 else 'red',
            'url': f'/clients/{client.id}/',
        })
    
    # ==========================================
    # 2. ПОИСК ЗАКАЗОВ (по номеру)
    # ==========================================
    from apps.rental.models import RentalOrder
    
    orders_query = RentalOrder.objects.select_related('client')
    
    # Если введено число - ищем по ID
    if query.isdigit():
        orders = orders_query.filter(id=int(query))[:5]
    else:
        # Ищем по имени клиента
        orders = orders_query.filter(
            Q(client__first_name__icontains=query) |
            Q(client__last_name__icontains=query) |
            Q(notes__icontains=query)
        )[:5]
    
    for order in orders:
        status_text = '🟢 Открыт' if order.status == 'open' else '⚪ Закрыт'
        total = int(order.get_current_total())
        
        results.append({
            'type': 'order',
            'icon': '📦',
            'title': f'Заказ #{order.id} — {order.client.get_full_name()}',
            'subtitle': f'{status_text} • {order.created_at.strftime("%d.%m.%Y")}',
            'badge': f'{total:,} сом'.replace(',', ' '),
            'badge_color': 'blue',
            'url': f'/clients/{order.client.id}/',
        })
    
    # ==========================================
    # 3. ПОИСК ТОВАРОВ (по названию)
    # ==========================================
    from apps.rental.models import Product
    
    products = Product.objects.filter(
        Q(name__icontains=query)
    )[:5]
    
    for product in products:
        results.append({
            'type': 'product',
            'icon': '🔧',
            'title': product.name,
            'subtitle': f'Доступно: {product.quantity_available} шт',
            'badge': f'{int(product.price_per_day):,} сом/день'.replace(',', ' '),
            'badge_color': 'purple',
            'url': f'/admin/rental/product/{product.id}/change/',
        })
    
    return JsonResponse({
        'results': results,
        'query': query,
        'total': len(results),
    })

def send_overdue_notification(request, order_id):
    '''Ручная отправка уведомления о просрочке'''
    from apps.rental.models import RentalOrder
    from apps.main.telegram_bot_complete import notify_overdue
    
    order = get_object_or_404(RentalOrder, id=order_id)
    
    # Отправляем уведомление
    notify_overdue(order)
    
    messages.success(request, f'Уведомление отправлено для заказа #{order_id}')
    
    return redirect('main:client_detail', client_id=order.client.id)



@staff_member_required
def edit_order_item_date(request, item_id):
    '''Изменить дату возврата позиции (только админ)'''
    from apps.rental.models import OrderItem
    from datetime import datetime
    
    item = get_object_or_404(OrderItem, id=item_id)
    
    if request.method == 'POST':
        new_date_str = request.POST.get('planned_return_date')
        
        try:
            # Парсим дату из формата datetime-local: 2026-02-25T14:30
            new_date = datetime.strptime(new_date_str, '%Y-%m-%dT%H:%M')
            
            # Делаем timezone aware
            from django.utils import timezone
            new_date = timezone.make_aware(new_date)
            
            item.planned_return_date = new_date
            item.save()
            
            messages.success(request, f'Дата возврата обновлена на {new_date.strftime("%d.%m.%Y %H:%M")}')
            return redirect('main:client_detail', client_id=item.order.client.id)
            
        except ValueError:
            messages.error(request, 'Неверный формат даты')
    
    context = {
        'item': item,
        'order': item.order,
        'client': item.order.client,
    }
    return render(request, 'rental/edit_item_date.html', context)

def create_product(request):
    '''Создать новый товар'''
    if request.method == 'POST':
        name = request.POST.get('name')
        price_per_day = request.POST.get('price_per_day')
        quantity = request.POST.get('quantity')
        
        product = Product.objects.create(
            name=name,
            price_per_day=price_per_day,
            quantity_available=quantity
        )
        
        messages.success(request, f'Товар "{product.name}" создан!')
        return redirect('/admin/rental/product/')
    
    return render(request, 'rental/create_product.html')