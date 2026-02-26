from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count, Q
from apps.clients.models import Client
from apps.rental.models import RentalOrder, OrderItem, Payment, ReturnDocument, Product
from apps.inventory.models import Product, Category
from datetime import datetime, timedelta
from django.utils import timezone
import json, os
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, FileResponse, Http404
from apps.rental.utils import get_order_groups_for_client
from config import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group, Permission
from .decorators import admin_required, manager_required, cashier_required
from django.contrib.auth import login, authenticate

def register_view(request):
    """Страница регистрации"""
    if request.user.is_authenticated:
        return redirect('main:setup_company')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        email = request.POST.get('email')
        
        # Валидация
        if not username or not password:
            messages.error(request, 'Заполните все поля')
            return render(request, 'registration/register.html')
        
        if password != password_confirm:
            messages.error(request, 'Пароли не совпадают')
            return render(request, 'registration/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует')
            return render(request, 'registration/register.html')
        
        # Создаём пользователя
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # Делаем первого пользователя администратором
        if User.objects.count() == 1:
            user.is_staff = True
            user.is_superuser = True
            admin_group, _ = Group.objects.get_or_create(name='Администратор')
            user.groups.add(admin_group)
            user.save()
        
        # Автоматический вход
        login(request, user)
        
        messages.success(request, 'Регистрация успешна! Настройте профиль компании.')
        return redirect('main:setup_company')
    
    return render(request, 'registration/register.html')


@login_required
def setup_company(request):
    """Страница настройки компании"""
    from apps.company.models import CompanyProfile
    
    company = CompanyProfile.get_company()
    
    if request.method == 'POST':
        # Обновляем данные компании
        company.company_name = request.POST.get('company_name')
        company.short_name = request.POST.get('short_name', '')
        company.phone = request.POST.get('phone', '')
        company.email = request.POST.get('email', '')
        company.address = request.POST.get('address', '')
        company.city = request.POST.get('city', '')
        company.inn = request.POST.get('inn', '')
        company.currency = request.POST.get('currency', 'сом')
        
        # Логотип
        if 'logo' in request.FILES:
            company.logo = request.FILES['logo']
        
        company.created_by = request.user
        company.save()
        
        messages.success(request, '✅ Профиль компании настроен!')
        return redirect('main:dashboard')
    
    context = {
        'company': company,
    }
    
    return render(request, 'main/setup_company.html', context)


@login_required
def edit_company(request):
    """Редактирование профиля компании"""
    from apps.company.models import CompanyProfile
    
    if not request.user.is_staff:
        messages.error(request, 'У вас нет прав на редактирование профиля компании')
        return redirect('main:dashboard')
    
    company = CompanyProfile.get_company()
    
    if request.method == 'POST':
        company.company_name = request.POST.get('company_name')
        company.short_name = request.POST.get('short_name', '')
        company.phone = request.POST.get('phone', '')
        company.email = request.POST.get('email', '')
        company.website = request.POST.get('website', '')
        company.address = request.POST.get('address', '')
        company.city = request.POST.get('city', '')
        company.inn = request.POST.get('inn', '')
        company.bank_account = request.POST.get('bank_account', '')
        company.bank_name = request.POST.get('bank_name', '')
        company.currency = request.POST.get('currency', 'сом')
        company.footer_text = request.POST.get('footer_text', '')
        
        if 'logo' in request.FILES:
            company.logo = request.FILES['logo']
        
        company.save()
        
        messages.success(request, '✅ Профиль компании обновлён!')
        return redirect('main:edit_company')
    
    context = {
        'company': company,
    }
    
    return render(request, 'main/edit_company.html', context)



@login_required
def dashboard(request):
    """Современный дашборд с графиками"""
    from django.db.models import Sum
    from decimal import Decimal
    
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # === СТАТИСТИКА ===
    total_clients = Client.objects.count()
    new_clients_week = Client.objects.filter(created_at__gte=week_ago).count()
    
    active_orders = RentalOrder.objects.filter(status='open').count()
    total_orders = RentalOrder.objects.count()
    
    # === ДОЛГИ (правильный расчёт через клиентов) ===
    # Общий долг = сумма долгов всех клиентов
    total_debt = sum(float(c.get_debt()) for c in Client.objects.all())
    
    # Должники (у кого баланс < 0)
    debtors_count = sum(1 for c in Client.objects.all() if c.get_wallet_balance() < 0)
    
    # === ДОХОД ===
    total_payments = Payment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    revenue_month = float(total_payments)
    
    # Рост дохода
    prev_month_start = month_ago - timedelta(days=30)
    revenue_prev_month = Payment.objects.filter(
        payment_date__gte=prev_month_start,
        payment_date__lt=month_ago
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    revenue_prev_float = float(revenue_prev_month)
    if revenue_prev_float > 0:
        revenue_growth = int(((revenue_month - revenue_prev_float) / revenue_prev_float) * 100)
    else:
        revenue_growth = 100 if revenue_month > 0 else 0
    
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
    # Оплачено всего
    total_paid = float(total_payments)
    
    # Аванс (переплата) = сумма кредитов всех клиентов
    total_credit = sum(float(c.get_credit()) for c in Client.objects.all())
    
    # Для диаграммы: оплачено, долги, аванс
    # Но долги уже включены в "оплачено" как неоплаченная часть
    # Поэтому показываем: реально оплачено vs ещё должен
    
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
    for order in RentalOrder.objects.filter(status='open').prefetch_related('items__product', 'client')[:50]:
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
    
    overdue_orders.sort(key=lambda x: x['days_overdue'], reverse=True)
    
    # context = {
    #     'now': now,
    #     'total_clients': total_clients,
    #     'new_clients_week': new_clients_week,
    #     'active_orders': active_orders,
    #     'total_orders': total_orders,
    #     'total_debt': total_debt,
    #     'debtors_count': debtors_count,
    #     'revenue_month': revenue_month,
    #     'revenue_growth': revenue_growth,
    #     'revenue_labels': json.dumps(revenue_labels),
    #     'revenue_data': json.dumps(revenue_data),
    #     'total_paid': total_paid,
    #     'debt_for_chart': total_debt,  # Для круговой диаграммы
    #     'total_credit': total_credit,
    #     'orders_labels': json.dumps(orders_labels),
    #     'orders_open_data': json.dumps(orders_open_data),
    #     'orders_closed_data': json.dumps(orders_closed_data),
    #     'top_products': top_products,
    #     'overdue_orders': overdue_orders,
    # }
    
    return render(request, 'main/dashboard.html', locals())

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
    from django.utils import timezone
    
    client = get_object_or_404(Client, id=client_id)
    now = timezone.now()
    
    active_orders = client.rental_orders.filter(status='open').prefetch_related('items__product')
    all_orders = client.rental_orders.all().order_by('-created_at')
    payments = client.payments.all().order_by('-payment_date')[:10]
    
    # Используем общую функцию
    order_groups = get_order_groups_for_client(client, now)
    # Группируем заказы
    for group in order_groups:
        order = group['order']
        
        # ДОБАВЬ ЭТО: Получаем все платежи по заказу
        group['payments'] = []
        for payment in client.payments.all():
            if payment.notes and f'#{order.id}' in payment.notes:
                group['payments'].append(payment)
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
        'now': now,
    }

    return render(request, 'clients/detail.html', context)

@login_required
def client_payments(request, client_id):
    """Все платежи клиента"""
    client = get_object_or_404(Client, id=client_id)
    
    # Получаем все платежи клиента, сортируем по дате (новые первые)
    payments = client.payments.all().order_by('-payment_date')
    
    context = {
        'client': client,
        'payments': payments,
        'total_paid': client.get_total_paid(),
        'wallet_balance': client.get_wallet_balance(),
    }
    
    return render(request, 'payments/client_payments.html', context)

@manager_required
def create_order(request):
    """Создание нового заказа"""
    from apps.clients.models import Client
    from apps.inventory.models import Product
    from apps.rental.models import RentalOrder, OrderItem
    
    # GET запрос - показываем форму
    if request.method == 'GET':
        # Получаем всех клиентов
        clients = Client.objects.prefetch_related('phones').all()
        
        # Получаем все доступные товары
        products = Product.objects.filter(quantity_available__gt=0)
        
        context = {
            'clients': clients,
            'products': products,
        }
        
        return render(request, 'rental/create_order.html', context)
    
    # POST запрос - обрабатываем форму
    if request.method == 'POST':
        try:
            # Получаем данные из формы
            client_id = request.POST.get('client')
            product_ids = request.POST.getlist('products[]')
            quantities = request.POST.getlist('quantities[]')
            days = request.POST.getlist('days[]')
            hours = request.POST.getlist('hours[]')
            
            # Валидация
            if not client_id:
                messages.error(request, 'Выберите клиента')
                return redirect('create_order')
            
            if not product_ids or not product_ids[0]:
                messages.error(request, 'Добавьте хотя бы один товар')
                return redirect('create_order')
            
            # Получаем клиента
            client = Client.objects.get(id=client_id)
            
            # Создаём заказ
            order = RentalOrder.objects.create(
                client=client,
                status='open'
            )
            
            # Добавляем товары в заказ
            for i, product_id in enumerate(product_ids):
                if not product_id:  # Пропускаем пустые
                    continue
                
                product = Product.objects.get(id=product_id)
                quantity = int(quantities[i])
                rental_days = int(days[i])
                rental_hours = int(hours[i])
                
                # Проверяем доступность
                if product.quantity_available < quantity:
                    messages.error(request, f'Недостаточно товара "{product.name}". Доступно: {product.quantity_available}')
                    order.delete()
                    return redirect('create_order')
                
                # Дата выдачи - сейчас
                issued_date = timezone.now()
                
                # Планируемая дата возврата
                planned_return_date = issued_date + timedelta(days=rental_days, hours=rental_hours)
                
                # Цены
                price_per_day = product.price_per_day
                price_per_hour = product.price_per_hour if hasattr(product, 'price_per_hour') else (price_per_day / 24)
                
                # Изначальная стоимость
                original_cost = quantity * (price_per_day * rental_days + price_per_hour * rental_hours)
                
                # Создаём позицию заказа
                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity_taken=quantity,
                    quantity_remaining=quantity,
                    issued_date=issued_date,
                    planned_return_date=planned_return_date,
                    rental_days=rental_days,
                    rental_hours=rental_hours,
                    price_per_day=price_per_day,
                    price_per_hour=price_per_hour,
                    original_total_cost=original_cost,
                    current_total_cost=original_cost,
                )
                
                # Уменьшаем доступное количество товара
                product.quantity_available -= quantity
                product.save()
            
            messages.success(request, f'✅ Заказ #{order.id} успешно создан!')
            
            # Редирект на страницу клиента
            return redirect('main:client_detail', client_id=client.id)
            
        except Client.DoesNotExist:
            messages.error(request, 'Клиент не найден')
            return redirect('create_order')
        
        except Product.DoesNotExist:
            messages.error(request, 'Товар не найден')
            return redirect('create_order')
        
        except Exception as e:
            messages.error(request, f'Ошибка создания заказа: {e}')
            return redirect('create_order')
        
@login_required
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


@cashier_required

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
    from django.utils import timezone
    
    selected_client_id = request.GET.get('client_id', '')
    clients = Client.objects.all().order_by('last_name', 'first_name')
    
    if not selected_client_id:
        context = {
            'clients': clients,
            'selected_client': None,
            'order_groups': [],
        }
        return render(request, 'main/history.html', context)
    
    try:
        selected_client = Client.objects.get(id=selected_client_id)
    except Client.DoesNotExist:
        return redirect('main:history')
    
    now = timezone.now()
    order_groups = get_order_groups_for_client(selected_client, now)
    
    context = {
        'clients': clients,
        'selected_client': selected_client,
        'selected_client_id': selected_client_id,
        'order_groups': order_groups,
        'wallet_balance': selected_client.get_wallet_balance(),
        'total_paid': selected_client.get_total_paid(),
        'total_debt': selected_client.get_total_debt(),
    }
    
    return render(request, 'main/history.html', context)
@manager_required
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

@cashier_required
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

@manager_required
def close_order(request, order_id):
    """Закрыть заказ вручную - все товары возвращаются на склад"""
    from apps.rental.models import ReturnDocument, ReturnItem
    from django.utils import timezone
    from decimal import Decimal
    
    order = get_object_or_404(RentalOrder, id=order_id)
    
    if order.status != 'open':
        return redirect('main:client_detail', client_id=order.client.id)
    
    now = timezone.now()
    items_to_return = list(order.items.filter(quantity_remaining__gt=0))
    
    if items_to_return:
        return_doc = ReturnDocument.objects.create(
            notes=f'Автоматический возврат при закрытии заказа #{order.id}',
            return_date=now
        )
        
        for item in items_to_return:
            delta = now - item.issued_date
            total_seconds = delta.total_seconds()
            actual_days = int(total_seconds // 86400)
            remaining_seconds = total_seconds % 86400
            actual_hours = int(remaining_seconds // 3600)
            
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
            
            # Обновляем OrderItem полностью
            item.quantity_returned += item.quantity_remaining
            item.quantity_remaining = 0
            item.actual_cost = calculated_cost
            item.current_total_cost = calculated_cost  # <-- ИСПРАВЛЕНИЕ
            item.save()
            
            product = item.product
            product.quantity_available += item.quantity_taken
            product.save()
    
    order.status = 'closed'
    order.save()
    
    messages.success(request, f'Заказ #{order.id} закрыт. Все товары возвращены на склад.')
    return redirect('main:client_detail', client_id=order.client.id)

from django.db.models.functions import Lower

def global_search(request):
    """Глобальный поиск - фильтрация в Python (работает всегда!)"""
    
    query = request.GET.get('q', '').strip()
    
    print(f"🔍 Поиск: '{query}'")
    
    if len(query) < 2:
        return JsonResponse({
            'clients': [],
            'orders': [],
            'products': []
        })
    
    from apps.clients.models import Client
    from apps.rental.models import RentalOrder
    from apps.inventory.models import Product
    
    # Приводим к нижнему регистру для поиска
    query_lower = query.lower()
    
    # ============================================================
    # ПОИСК КЛИЕНТОВ В PYTHON
    # ============================================================
    
    # Получаем всех клиентов (или последних 200 для скорости)
    all_clients = Client.objects.prefetch_related('phones').all()
    
    found_clients = []
    for client in all_clients:
        # Проверяем в Python (точно работает!)
        match = False
        
        # Проверяем имя
        if client.first_name and query_lower in client.first_name.lower():
            match = True
        
        # Проверяем фамилию
        if client.last_name and query_lower in client.last_name.lower():
            match = True
        
        # Проверяем отчество
        if client.middle_name and query_lower in client.middle_name.lower():
            match = True
        
        # Проверяем телефоны
        for phone in client.phones.all():
            if query in phone.phone_number:
                match = True
                break
        
        if match:
            found_clients.append(client)
            print(f"  ✅ Найден: {client.get_full_name()}")
            
            # Ограничиваем 5 результатами
            if len(found_clients) >= 5:
                break
    
    print(f"📊 Всего найдено клиентов: {len(found_clients)}")
    
    # Формируем результаты
    clients_results = []
    for client in found_clients:
        try:
            balance = float(client.get_wallet_balance())
            badge_color = 'bg-green-100 text-green-700' if balance >= 0 else 'bg-red-100 text-red-700'
            badge_text = f'+{int(balance)}' if balance > 0 else f'{int(balance)}'
            
            phones = ', '.join([p.phone_number for p in client.phones.all()[:2]])
            
            clients_results.append({
                'type': 'client',
                'title': client.get_full_name(),
                'subtitle': phones,
                'badge': f'{badge_text} сом',
                'badge_color': badge_color,
                'url': f'/clients/{client.id}/',
            })
        except Exception as e:
            print(f"❌ Ошибка формирования результата: {e}")
    
    # ============================================================
    # ПОИСК ЗАКАЗОВ В PYTHON
    # ============================================================
    
    found_orders = []
    
    # Если это число - ищем по ID
    try:
        order_id = int(query)
        found_orders = list(RentalOrder.objects.filter(id=order_id).select_related('client')[:5])
    except ValueError:
        # Иначе ищем по клиенту
        all_orders = RentalOrder.objects.select_related('client').prefetch_related('client__phones').all()[:100]
        
        for order in all_orders:
            match = False
            
            # Ищем в имени клиента
            if order.client.first_name and query_lower in order.client.first_name.lower():
                match = True
            if order.client.last_name and query_lower in order.client.last_name.lower():
                match = True
            
            # Ищем в примечаниях
            if order.notes and query_lower in order.notes.lower():
                match = True
            
            if match:
                found_orders.append(order)
                if len(found_orders) >= 5:
                    break
    
    orders_results = []
    for order in found_orders:
        try:
            badge_color = 'bg-blue-100 text-blue-700' if order.status == 'open' else 'bg-gray-100 text-gray-700'
            badge_text = 'Открыт' if order.status == 'open' else 'Закрыт'
            
            orders_results.append({
                'type': 'order',
                'title': f'Заказ #{order.id}',
                'subtitle': f'{order.client.get_full_name()} • {order.created_at.strftime("%d.%m.%Y")}',
                'badge': badge_text,
                'badge_color': badge_color,
                'url': f'/clients/{order.client.id}/',
            })
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # ============================================================
    # ПОИСК ТОВАРОВ В PYTHON
    # ============================================================
    
    all_products = Product.objects.all()
    found_products = []
    
    for product in all_products:
        if product.name and query_lower in product.name.lower():
            found_products.append(product)
            if len(found_products) >= 5:
                break
    
    products_results = []
    for product in found_products:
        try:
            products_results.append({
                'type': 'product',
                'title': product.name,
                'subtitle': f'{product.price_per_day} сом/день',
                'badge': f'{product.quantity_available} шт',
                'badge_color': 'bg-purple-100 text-purple-700',
                'url': f'/admin/inventory/product/{product.id}/change/',
            })
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    print(f"📤 Возвращаем: {len(clients_results)} клиентов, {len(orders_results)} заказов, {len(products_results)} товаров")
    
    return JsonResponse({
        'clients': clients_results,
        'orders': orders_results,
        'products': products_results,
    }, json_dumps_params={'ensure_ascii': False})

def global_search_optimized(request):
    """Оптимизированный поиск для больших баз"""
    
    query = request.GET.get('q', '').strip().lower()
    
    if len(query) < 2:
        return JsonResponse({'clients': [], 'orders': [], 'products': []})
    
    from apps.clients.models import Client
    
    # Берём только последних 500 клиентов (самые свежие)
    all_clients = Client.objects.prefetch_related('phones').order_by('-id')[:500]
    
    found_clients = []
    for client in all_clients:
        # Ищем в полном имени сразу (быстрее)
        full_name = f"{client.first_name} {client.last_name} {client.middle_name or ''}".lower()
        
        if query in full_name:
            found_clients.append(client)
            if len(found_clients) >= 5:
                break
    
    
    clients_results = []
    for client in found_clients:
        balance = float(client.get_wallet_balance())
        badge_color = 'bg-green-100 text-green-700' if balance >= 0 else 'bg-red-100 text-red-700'
        badge_text = f'+{int(balance)}' if balance > 0 else f'{int(balance)}'
        phones = ', '.join([p.phone_number for p in client.phones.all()[:2]])
        
        clients_results.append({
            'type': 'client',
            'title': client.get_full_name(),
            'subtitle': phones,
            'badge': f'{badge_text} сом',
            'badge_color': badge_color,
            'url': f'/clients/{client.id}/',
        })
    
    return JsonResponse({
        'clients': clients_results,
        'orders': [],
        'products': [],
    }, json_dumps_params={'ensure_ascii': False})

def send_overdue_notification(request, order_id):
    '''Ручная отправка уведомления о просрочке'''
    from apps.rental.models import RentalOrder
    from apps.main.telegram_bot_complete import notify_overdue
    
    order = get_object_or_404(RentalOrder, id=order_id)
    
    # Отправляем уведомление
    notify_overdue(order)
    
    messages.success(request, f'Уведомление отправлено для заказа #{order_id}')
    
    return redirect('main:client_detail', client_id=order.client.id)



@admin_required
def edit_order_dates(request, order_id):
    """Изменить даты возврата товаров в заказе (можно выбрать несколько) с отслеживанием в истории"""
    from apps.rental.models import RentalOrder, OrderItem
    from decimal import Decimal
    from datetime import timedelta

    order = get_object_or_404(RentalOrder, id=order_id)

    # Получаем все невозвращённые товары в заказе
    items = order.items.filter(quantity_remaining__gt=0)

    if request.method == 'POST':
        # Получаем выбранные товары
        selected_items = request.POST.getlist('items')  # Список ID товаров
        new_date_str = request.POST.get('new_date')

        if not selected_items:
            messages.error(request, 'Выберите хотя бы один товар')
            return redirect(request.path)

        if not new_date_str:
            messages.error(request, 'Укажите новую дату')
            return redirect(request.path)

        try:
            # Парсим дату
            new_date = datetime.strptime(new_date_str, '%Y-%m-%dT%H:%M')
            new_date = timezone.make_aware(new_date)

            # Обновляем даты для выбранных товаров и собираем информацию об изменениях
            updated_count = 0
            changes_log = []  # Список изменений для истории

            for item_id in selected_items:
                try:
                    item = OrderItem.objects.get(id=int(item_id), order=order)
                    old_date = item.planned_return_date

                    # Вычисляем старую и новую стоимость
                    # Используем quantity_taken (взятое количество), а не quantity_remaining
                    quantity = Decimal(item.quantity_taken)

                    # Старая стоимость (по старой дате)
                    old_delta = old_date - item.issued_date
                    old_total_hours = int(old_delta.total_seconds() / 3600)
                    old_days = old_total_hours // 24
                    old_hours = old_total_hours % 24
                    old_cost = quantity * (
                        Decimal(item.price_per_day) * old_days +
                        Decimal(item.price_per_hour) * old_hours
                    )

                    # Новая стоимость (по новой дате)
                    new_delta = new_date - item.issued_date
                    new_total_hours = int(new_delta.total_seconds() / 3600)
                    new_days = new_total_hours // 24
                    new_hours = new_total_hours % 24
                    new_cost = quantity * (
                        Decimal(item.price_per_day) * new_days +
                        Decimal(item.price_per_hour) * new_hours
                    )

                    # Разница стоимости
                    cost_difference = new_cost - old_cost

                    # Обновляем дату И стоимость
                    item.planned_return_date = new_date
                    item.current_total_cost = new_cost  # Обновляем сумму!
                    item.save()
                    updated_count += 1

                    # Формируем информацию об изменении для истории
                    old_date_str = old_date.strftime('%d.%m.%Y %H:%M')
                    new_date_str_formatted = new_date.strftime('%d.%m.%Y %H:%M')

                    change_info = {
                        'product_name': item.product.name,
                        'quantity': item.quantity_remaining,
                        'old_date': old_date_str,
                        'new_date': new_date_str_formatted,
                        'old_cost': float(old_cost),
                        'new_cost': float(new_cost),
                        'cost_difference': float(cost_difference),
                    }
                    changes_log.append(change_info)

                    print(f"✅ Обновлён товар {item.product.name}: {old_date} → {new_date}, разница: {cost_difference:.0f} сом")
                except OrderItem.DoesNotExist:
                    print(f"❌ Товар {item_id} не найден")

            # Добавляем информацию об изменениях в историю (в notes заказа)
            if changes_log:
                # Формируем текст истории
                history_lines = []
                total_diff = 0
                for change in changes_log:
                    diff_symbol = '+' if change['cost_difference'] >= 0 else ''
                    history_lines.append(
                        f"📅 Изменение даты: {change['product_name']} x{change['quantity']} - "
                        f"с {change['old_date']} на {change['new_date']} "
                        f"(сумма: {diff_symbol}{change['cost_difference']:.0f} сом)"
                    )
                    total_diff += change['cost_difference']

                # Добавляем в notes заказа
                history_text = "\n".join(history_lines)
                if order.notes:
                    order.notes = f"{order.notes}\n\n{history_text}"
                else:
                    order.notes = history_text
                order.save()

                # Сообщение пользователю
                diff_symbol = '+' if total_diff >= 0 else ''
                messages.success(
                    request,
                    f'Дата возврата обновлена для {updated_count} товаров на {new_date.strftime("%d.%m.%Y %H:%M")}. '
                    f'Итоговая корректировка суммы: {diff_symbol}{total_diff:.0f} сом'
                )
            else:
                messages.success(request, f'Дата возврата обновлена для {updated_count} товаров на {new_date.strftime("%d.%m.%Y %H:%M")}')

            return redirect('main:client_detail', client_id=order.client.id)

        except ValueError as e:
            messages.error(request, f'Неверный формат даты: {e}')

    context = {
        'order': order,
        'client': order.client,
        'items': items,
    }

    return render(request, 'rental/edit_item_date.html', context)

@manager_required
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

def orders_calendar(request):
    """Календарь заказов"""
    from apps.rental.models import RentalOrder
    from apps.clients.models import Client

    # Получаем выбранного клиента
    selected_client_id = request.GET.get('client_id')
    selected_client_id_int = int(selected_client_id) if selected_client_id else None

    # Базовый запрос - все активные заказы
    orders = RentalOrder.objects.filter(
        status='open'
    ).select_related('client').prefetch_related('items__product', 'client__phones')

    # Фильтрация по клиенту
    if selected_client_id_int:
        orders = orders.filter(client_id=selected_client_id_int)

    # Получаем список всех клиентов для выпадающего списка
    clients = Client.objects.filter(
        rental_orders__status='open'
    ).distinct().order_by('last_name', 'first_name')

    # Подсчет активных и просроченных
    now = timezone.now()
    active_count = 0
    overdue_count = 0

    # Формируем события для календаря
    events = []

    for order in orders:
        for item in order.items.filter(quantity_remaining__gt=0):

            # Определяем статус - просрочен или нет
            is_overdue = item.planned_return_date < now

            if is_overdue:
                overdue_count += 1
                status = 'overdue'
            else:
                active_count += 1
                status = 'active'

            # Выдача (pickup) - синий
            events.append({
                'id': f'order_{order.id}_item_{item.id}_pickup',
                'title': f'{item.product.name} x{item.quantity_remaining}',
                'start': item.issued_date.isoformat(),
                'allDay': True,
                'backgroundColor': '#3b82f6',
                'borderColor': '#3b82f6',
                'extendedProps': {
                    'client_name': order.client.get_full_name(),
                    'client_id': order.client.id,
                    'order_id': order.id,
                    'product_name': item.product.name,
                    'quantity': item.quantity_remaining,
                    'phone': ', '.join([p.phone_number for p in order.client.phones.all()]),
                    'status': status,
                    'event_type': 'pickup',
                    'issued_date': item.issued_date.isoformat(),
                    'planned_return_date': item.planned_return_date.isoformat(),
                }
            })

            # Возврат (return) - зеленый или красный если просрочен
            events.append({
                'id': f'order_{order.id}_item_{item.id}_return',
                'title': f'{item.product.name} x{item.quantity_remaining}',
                'start': item.planned_return_date.isoformat(),
                'allDay': True,
                'backgroundColor': '#ef4444' if is_overdue else '#10b981',
                'borderColor': '#ef4444' if is_overdue else '#10b981',
                'extendedProps': {
                    'client_name': order.client.get_full_name(),
                    'client_id': order.client.id,
                    'order_id': order.id,
                    'product_name': item.product.name,
                    'quantity': item.quantity_remaining,
                    'phone': ', '.join([p.phone_number for p in order.client.phones.all()]),
                    'status': status,
                    'event_type': 'return',
                    'issued_date': item.issued_date.isoformat(),
                    'planned_return_date': item.planned_return_date.isoformat(),
                }
            })

    context = {
        'events_json': json.dumps(events, ensure_ascii=False),
        'active_count': active_count,
        'overdue_count': overdue_count,
        'clients': clients,
        'selected_client_id': selected_client_id_int,
    }

    return render(request, 'main/calendar.html', context)


@staff_member_required
def download_latest_backup(request):
    """Скачать последний бэкап"""
    
    backup_dir = os.path.join(settings.BASE_DIR, 'backups')
    
    # Находим последний бэкап
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith('db_backup_') and filename.endswith('.sqlite3'):
            filepath = os.path.join(backup_dir, filename)
            backups.append((filepath, os.path.getmtime(filepath)))
    
    if not backups:
        raise Http404('Бэкапы не найдены')
    
    # Последний файл
    backups.sort(key=lambda x: x[1], reverse=True)
    latest_backup = backups[0][0]
    
    # Отдаём файл
    response = FileResponse(open(latest_backup, 'rb'))
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(latest_backup)}"'
    
    return response


@staff_member_required
def create_backup_now(request):
    """Создать бэкап сейчас"""
    from django.core.management import call_command
    
    try:
        # Вызываем команду создания бэкапа
        call_command('backup_db')
        messages.success(request, '✅ Бэкап успешно создан!')
    except Exception as e:
        messages.error(request, f'❌ Ошибка создания бэкапа: {e}')
    
    return redirect('main:dashboard')

def is_admin(user):
    """Проверка что пользователь администратор"""
    return user.is_superuser or user.groups.filter(name='Администратор').exists()

@admin_required
def users_management(request):
    """Страница управления пользователями и ролями"""
    
    # Получаем всех пользователей
    users = User.objects.prefetch_related('groups', 'user_permissions').order_by('-date_joined')
    
    # Получаем все группы
    groups = Group.objects.prefetch_related('permissions').all()
    
    # Статистика по ролям
    stats = {
        'total_users': users.count(),
        'active_users': users.filter(is_active=True).count(),
        'admins': users.filter(Q(is_superuser=True) | Q(groups__name='Администратор')).distinct().count(),
        'managers': users.filter(groups__name='Менеджер').count(),
        'cashiers': users.filter(groups__name='Кассир').count(),
    }
    
    context = {
        'users': users,
        'groups': groups,
        'stats': stats,
    }
    
    return render(request, 'main/users_management.html', context)


@login_required
@user_passes_test(is_admin)
def toggle_user_active(request, user_id):
    """Активировать/деактивировать пользователя"""
    user = get_object_or_404(User, id=user_id)
    
    if user == request.user:
        messages.error(request, 'Нельзя деактивировать самого себя!')
        return redirect('main:users_management')
    
    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Нельзя деактивировать суперпользователя!')
        return redirect('main:users_management')
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'активирован' if user.is_active else 'деактивирован'
    messages.success(request, f'Пользователь {user.username} {status}')
    
    return redirect('main:users_management')


@login_required
@user_passes_test(is_admin)
def assign_user_group(request, user_id):
    """Назначить группу пользователю"""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        group_id = request.POST.get('group_id')
        
        if group_id:
            group = get_object_or_404(Group, id=group_id)
            user.groups.add(group)
            messages.success(request, f'Роль "{group.name}" назначена пользователю {user.username}')
        
        return redirect('main:users_management')


@login_required
@user_passes_test(is_admin)
def remove_user_group(request, user_id, group_id):
    """Удалить группу у пользователя"""
    user = get_object_or_404(User, id=user_id)
    group = get_object_or_404(Group, id=group_id)
    
    user.groups.remove(group)
    messages.success(request, f'Роль "{group.name}" удалена у пользователя {user.username}')
    
    return redirect('main:users_management')


@admin_required
def permissions_matrix(request):
    """Матрица прав доступа"""
    
    # Получаем все группы
    groups = Group.objects.prefetch_related('permissions').all()
    
    # Получаем основные разрешения
    permission_categories = {
        'Клиенты': Permission.objects.filter(content_type__model='client'),
        'Заказы': Permission.objects.filter(content_type__model='rentalorder'),
        'Товары': Permission.objects.filter(content_type__model='product'),
        'Платежи': Permission.objects.filter(content_type__model='payment'),
        'Возвраты': Permission.objects.filter(content_type__model='returndocument'),
    }
    
    context = {
        'groups': groups,
        'permission_categories': permission_categories,
    }
    
    return render(request, 'main/permissions_matrix.html', context)
