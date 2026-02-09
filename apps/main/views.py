# apps/main/views.py
# -*- coding: utf-8 -*-
"""
Views для пользовательского интерфейса
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count, Q
from apps.clients.models import Client
from apps.rental.models import RentalOrder, OrderItem, Payment, ReturnDocument
from apps.inventory.models import Product, Category
from datetime import datetime, timedelta
from django.utils import timezone


def dashboard(request):
    """Главная страница (Dashboard)"""
    
    # Статистика
    total_clients = Client.objects.count()
    active_orders = RentalOrder.objects.filter(status='open').count()
    
    # Общий долг всех клиентов
    total_debt = 0
    for client in Client.objects.all():
        debt = client.get_debt()
        total_debt += debt
    
    # Последние заказы
    recent_orders = RentalOrder.objects.select_related('client').order_by('-created_at')[:10]
    
    # Топ должники
    clients_with_debt = []
    for client in Client.objects.all():
        debt = client.get_debt()
        if debt > 0:
            clients_with_debt.append({
                'client': client,
                'debt': debt
            })
    # Сортируем по долгу
    clients_with_debt = sorted(clients_with_debt, key=lambda x: x['debt'], reverse=True)[:5]
    
    context = {
        'total_clients': total_clients,
        'active_orders': active_orders,
        'total_debt': int(total_debt),
        'recent_orders': recent_orders,
        'top_debtors': clients_with_debt,
    }
    
    return render(request, 'main/dashboard.html', context)


def clients_list(request):
    """Список клиентов"""
    
    query = request.GET.get('q', '')
    
    clients = Client.objects.prefetch_related('phones').all()
    
    # Поиск
    if query:
        clients = clients.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(phones__phone_number__icontains=query)
        ).distinct()
    
    # Добавляем баланс к каждому клиенту
    clients_data = []
    for client in clients:
        clients_data.append({
            'client': client,
            'balance': client.get_wallet_balance(),
            'debt': client.get_debt(),
            'active_orders': client.get_active_orders().count()
        })
    
    context = {
        'clients_data': clients_data,
        'query': query,
    }
    
    return render(request, 'clients/list.html', context)


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
        
        order_groups.append({
            'order': order,
            'events': order_events,
            'total_paid': total_paid_for_order,
            'current_cost': current_order_cost,
            'debt': order_debt,
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
        'order_groups': order_groups,  # ← ДОБАВИЛИ ГРУППИРОВАННУЮ ИСТОРИЮ
    }
    
    return render(request, 'clients/detail.html', context)

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
    """Список заказов"""
    
    status_filter = request.GET.get('status', '')
    
    orders = RentalOrder.objects.select_related('client').prefetch_related('items__product').all()
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    orders = orders.order_by('-created_at')
    
    context = {
        'orders': orders,
        'status_filter': status_filter,
    }
    
    return render(request, 'rental/orders_list.html', context)




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

# apps/main/views.py
# ЗАМЕНИТЕ функцию history на эту ПРАВИЛЬНУЮ версию:

# apps/main/views.py
# ЗАМЕНИТЕ функцию history на эту ГРУППИРОВАННУЮ версию:

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
        
        order_groups.append({
            'order': order,
            'events': order_events,
            'total_paid': total_paid_for_order,
            'current_cost': current_order_cost,
            'debt': order_debt,
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
    """История операций по клиентам"""
    
    selected_client_id = request.GET.get('client_id', '')
    
    # Список всех клиентов
    clients = Client.objects.all().order_by('last_name', 'first_name')
    
    # Если клиент не выбран - показываем только форму выбора
    if not selected_client_id:
        context = {
            'clients': clients,
            'selected_client': None,
            'events': [],
        }
        return render(request, 'main/history.html', context)
    
    # Получаем выбранного клиента
    try:
        selected_client = Client.objects.get(id=selected_client_id)
    except Client.DoesNotExist:
        return redirect('main:history')
    
    # Собираем все события клиента
    events = []
    
    # 1. Заказы клиента
    orders = selected_client.rental_orders.all().order_by('-created_at')
    
    for order in orders:
        events.append({
            'type': 'order',
            'date': order.created_at,
            'description': f'Заказ #{order.id}',  # ← КОРОТКОЕ НАЗВАНИЕ
            'amount': -float(order.get_original_total()),
            'order': order,
            'items': list(order.items.all()),
        })
    
    # 2. Возвраты клиента
    from apps.rental.models import ReturnDocument
    
    # Получаем все возвраты через заказы клиента
    for order in orders:
        for order_item in order.items.all():
            for return_item in order_item.returns.all():
                events.append({
                    'type': 'return',
                    'date': return_item.return_document.return_date,
                    'description': f'Возврат #{order.id}',  # ← КОРОТКОЕ НАЗВАНИЕ
                    'amount': 0,
                    'return_item': return_item,
                    'order': order,
                })
    
    # 3. Оплаты клиента
    import re
    
    for payment in selected_client.payments.all().order_by('-payment_date'):  # ← ИСПРАВЛЕНО: selected_client
        # Извлекаем номера заказов из примечания
        order_numbers = []
        if payment.notes and 'Оплата для заказ' in payment.notes:
            # Находим все номера заказов в примечании
            matches = re.findall(r'#(\d+)', payment.notes.split('\n')[0])
            order_numbers = matches
        
        # Формируем описание
        if order_numbers:
            if len(order_numbers) == 1:
                description = f'Оплата для заказа #{order_numbers[0]}'
            else:
                description = f'Оплата для заказов #{", #".join(order_numbers)}'
        else:
            description = f'Оплата {payment.get_payment_method_display()}'
        
        events.append({
            'type': 'payment',
            'date': payment.payment_date,
            'description': description,
            'amount': float(payment.amount),
            'payment': payment,
            'order_numbers': order_numbers,
        })
    
    # Сортируем по дате (новые сверху)
    events.sort(key=lambda x: x['date'], reverse=True)
    
    # Баланс клиента
    wallet_balance = selected_client.get_wallet_balance()
    total_paid = selected_client.get_total_paid()
    total_debt = selected_client.get_total_debt()
    
    context = {
        'clients': clients,
        'selected_client': selected_client,
        'selected_client_id': selected_client_id,
        'events': events,
        'wallet_balance': wallet_balance,
        'total_paid': total_paid,
        'total_debt': total_debt,
    }
    
    return render(request, 'main/history.html', context)
    """История операций по клиентам"""
    
    selected_client_id = request.GET.get('client_id', '')
    
    # Список всех клиентов
    clients = Client.objects.all().order_by('last_name', 'first_name')
    
    # Если клиент не выбран - показываем только форму выбора
    if not selected_client_id:
        context = {
            'clients': clients,
            'selected_client': None,
            'events': [],
        }
        return render(request, 'main/history.html', context)
    
    # Получаем выбранного клиента
    try:
        selected_client = Client.objects.get(id=selected_client_id)
    except Client.DoesNotExist:
        return redirect('main:history')
    
    # Собираем все события клиента
    events = []
    
    # 1. Заказы клиента
    orders = selected_client.rental_orders.all().order_by('-created_at')
    
    for order in orders:
        events.append({
            'type': 'order',
            'date': order.created_at,
            'description': f'Создан заказ #{order.id}',
            'amount': -float(order.get_original_total()),
            'order': order,
            'items': list(order.items.all()),
        })
    
    # 2. Возвраты клиента
    from apps.rental.models import ReturnDocument
    
    # Получаем все возвраты через заказы клиента
    for order in orders:
        for order_item in order.items.all():
            for return_item in order_item.returns.all():
                events.append({
                    'type': 'return',
                    'date': return_item.return_document.return_date,
                    'description': f'Возврат по заказу #{order.id}',
                    'amount': 0,
                    'return_item': return_item,
                    'order': order,
                })
    
    # 3. Оплаты клиента
    payments = selected_client.payments.all().order_by('-payment_date')
    
    for payment in client.payments.all().order_by('-payment_date'):
    # Извлекаем номера заказов из примечания
        order_numbers = []
        if payment.notes and 'Оплата для заказ' in payment.notes:
            # Находим все номера заказов в примечании
            import re
            matches = re.findall(r'#(\d+)', payment.notes.split('\n')[0])
            order_numbers = matches
        
        # Формируем описание
        if order_numbers:
            if len(order_numbers) == 1:
                description = f'Оплата для заказа #{order_numbers[0]}'
            else:
                description = f'Оплата для заказов #{", #".join(order_numbers)}'
        else:
            description = f'Оплата {payment.get_payment_method_display()}'
        
        events.append({
            'type': 'payment',
            'date': payment.payment_date,
            'description': description,
            'amount': float(payment.amount),
            'payment': payment,
            'order_numbers': order_numbers,  # Для использования в шаблоне
        })
    
    # Сортируем по дате (новые сверху)
    events.sort(key=lambda x: x['date'], reverse=True)
    
    # Баланс клиента
    wallet_balance = selected_client.get_wallet_balance()
    total_paid = selected_client.get_total_paid()
    total_debt = selected_client.get_total_debt()
    
    context = {
        'clients': clients,
        'selected_client': selected_client,
        'selected_client_id': selected_client_id,
        'events': events,
        'wallet_balance': wallet_balance,
        'total_paid': total_paid,
        'total_debt': total_debt,
    }
    
    return render(request, 'main/history.html', context)