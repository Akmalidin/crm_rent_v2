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
from apps.rental.utils import get_order_groups_for_client, calculate_order_debt
from config import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group, Permission
from .decorators import admin_required, manager_required, cashier_required
from django.contrib.auth import login, authenticate
from apps.main.models import UserProfile


def get_tenant_owner(user):
    """
    Возвращает суперпользователя-владельца тенанта для данного user.
    Если user сам суперпользователь — возвращает себя.
    Если user — сотрудник — возвращает owner из его UserProfile.
    """
    if user.is_superuser:
        return user
    try:
        owner = user.profile.owner
        return owner if owner else user
    except Exception:
        return user


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
        
        # Первый пользователь = создатель системы
        is_first_user = not User.objects.filter(is_staff=True, is_superuser=True).exclude(id=user.id).exists()

        if is_first_user:
            # Создатель системы — полный доступ
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            admin_group, _ = Group.objects.get_or_create(name='Администратор')
            user.groups.add(admin_group)
            user.save()
            # UserProfile: owner=None → сам является владельцем своей компании
            UserProfile.objects.get_or_create(user=user, defaults={'owner': None})
        else:
            # Новая компания — ждёт одобрения создателем системы
            user.is_active = False
            user.is_staff = False
            user.is_superuser = False
            user.save()
            # Профиль: owner=None → станет владельцем своей компании после одобрения
            UserProfile.objects.get_or_create(user=user, defaults={'owner': None})

        # Уведомление администратора в Telegram о новой регистрации
        try:
            from apps.main.telegram_bot_complete import send_telegram_message
            admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
            if admin_chat_id:
                role_label = 'Администратор (первый пользователь)' if is_first_user else 'Новый пользователь (ожидает одобрения)'
                tg_text = (
                    f"🆕 <b>Новая регистрация</b>\n\n"
                    f"👤 Имя пользователя: <code>{username}</code>\n"
                    f"📧 Email: {email or '—'}\n"
                    f"🏷️ Роль: {role_label}\n\n"
                    f"⚠️ Перейдите в панель администратора чтобы одобрить пользователя."
                )
                send_telegram_message(admin_chat_id, tg_text)
        except Exception:
            pass

        if is_first_user:
            # Первый пользователь — входим сразу
            login(request, user)
            messages.success(request, 'Добро пожаловать! Вы зарегистрированы как администратор.')
            return redirect('main:setup_company')
        else:
            # Обычный пользователь — ждёт одобрения
            return redirect('main:pending_approval')
    
    return render(request, 'registration/register.html')


def pending_approval(request):
    """Страница ожидания одобрения аккаунта"""
    return render(request, 'registration/pending_approval.html')


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

    owner = get_tenant_owner(request.user)

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # === СТАТИСТИКА ===
    total_clients = Client.objects.filter(owner=owner).count()
    new_clients_week = Client.objects.filter(owner=owner, created_at__gte=week_ago).count()

    active_orders = RentalOrder.objects.filter(status='open', client__owner=owner).count()
    total_orders = RentalOrder.objects.filter(client__owner=owner).count()

    # === ДОЛГИ (правильный расчёт через клиентов) ===
    # Общий долг = сумма долгов всех клиентов
    total_debt = sum(float(c.get_debt()) for c in Client.objects.filter(owner=owner))

    # Должники (у кого баланс < 0)
    debtors_count = sum(1 for c in Client.objects.filter(owner=owner) if c.get_wallet_balance() < 0)

    # === ДОХОД ===
    total_payments = Payment.objects.filter(client__owner=owner).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    revenue_month = float(total_payments)

    # Рост дохода
    prev_month_start = month_ago - timedelta(days=30)
    revenue_prev_month = Payment.objects.filter(
        client__owner=owner,
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
            client__owner=owner,
            payment_date__date=day.date()
        ).aggregate(total=Sum('amount'))['total'] or 0
        revenue_data.append(float(day_revenue))

    # === КРУГОВАЯ ДИАГРАММА ===
    # Оплачено всего
    total_paid = float(total_payments)

    # Аванс (переплата) = сумма кредитов всех клиентов
    total_credit = sum(float(c.get_credit()) for c in Client.objects.filter(owner=owner))

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
            client__owner=owner,
            created_at__date=day.date(),
            status='open'
        ).count()
        closed_count = RentalOrder.objects.filter(
            client__owner=owner,
            created_at__date=day.date(),
            status='closed'
        ).count()

        orders_open_data.append(open_count)
        orders_closed_data.append(closed_count)

    # === ТОП-5 ТОВАРОВ ===
    products_stats = OrderItem.objects.filter(order__client__owner=owner).values('product__name').annotate(
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

    # === ЗАКАЗЫ ПО ДНЯМ НЕДЕЛИ ===
    weekday_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    weekday_counts = [0] * 7
    for order in RentalOrder.objects.filter(client__owner=owner):
        wd = order.created_at.weekday()  # 0=Mon, 6=Sun
        weekday_counts[wd] += 1
    weekday_labels = json.dumps(weekday_names)
    weekday_data = json.dumps(weekday_counts)

    # === ПРОСРОЧЕННЫЕ ЗАКАЗЫ ===
    overdue_orders = []
    for order in RentalOrder.objects.filter(status='open', client__owner=owner).prefetch_related('items__product', 'client')[:50]:
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

    owner = get_tenant_owner(request.user)

    # Параметры фильтров
    filter_type  = request.GET.get('filter', '')      # debt / credit / active / all
    date_range   = request.GET.get('date_range', '')  # today / week / month
    amount_min   = request.GET.get('amount_min', '')
    amount_max   = request.GET.get('amount_max', '')
    sort_by      = request.GET.get('sort', '-created_at')

    # Базовый queryset
    clients = Client.objects.filter(owner=owner).prefetch_related('phones', 'rental_orders')
    
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
    all_clients = Client.objects.filter(owner=owner).prefetch_related('phones', 'rental_orders')
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

    owner = get_tenant_owner(request.user)
    client = get_object_or_404(Client, id=client_id, owner=owner)
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

    order_id = request.GET.get('order')

    # Получаем платежи клиента, при необходимости фильтруем по конкретному заказу
    payments_query = client.payments.all()
    if order_id:
        try:
            order_id_int = int(order_id)
        except (TypeError, ValueError):
            order_id_int = None
        if order_id_int:
            payments_query = payments_query.filter(notes__icontains=f'#{order_id_int}')
    payments = payments_query.order_by('-payment_date')

    context = {
        'client': client,
        'payments': payments,
        'total_paid': client.get_total_paid(),
        'wallet_balance': client.get_wallet_balance(),
        'order_id': order_id,
    }
    
    return render(request, 'payments/client_payments.html', context)

@manager_required
def create_order(request):
    """Создание нового заказа"""
    from apps.clients.models import Client
    from apps.inventory.models import Product
    from apps.rental.models import RentalOrder, OrderItem

    owner = get_tenant_owner(request.user)

    # GET запрос - показываем форму
    if request.method == 'GET':
        # Получаем клиентов текущего тенанта
        clients = Client.objects.filter(owner=owner).prefetch_related('phones')

        # Получаем доступные товары текущего тенанта
        products = Product.objects.filter(owner=owner, quantity_available__gt=0)
        
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
            
            # Получаем клиента (только текущего тенанта)
            client = Client.objects.get(id=client_id, owner=owner)
            
            # Создаём заказ
            proof_file = request.FILES.get('proof_file')
            order = RentalOrder.objects.create(
                client=client,
                status='open',
                proof_file=proof_file,
            )
            
            # Добавляем товары в заказ
            for i, product_id in enumerate(product_ids):
                if not product_id:  # Пропускаем пустые
                    continue
                
                product = Product.objects.get(id=product_id, owner=owner)
                quantity = int(quantities[i])
                rental_days = int(days[i])
                rental_hours = int(hours[i])
                
                # Проверяем доступность
                if product.quantity_available < quantity:
                    messages.error(request, f'Недостаточно товара "{product.name}". Доступно: {product.quantity_available}')
                    order.delete()
                    return redirect('main:create_order')
                
                # Дата выдачи - сейчас
                issued_date = timezone.now()
                
                # Планируемая дата возврата
                planned_return_date = issued_date + timedelta(days=rental_days, hours=rental_hours)
                
                # Цены
                price_per_day = product.price_per_day
                price_per_hour = product.price_per_hour if (hasattr(product, 'price_per_hour') and product.price_per_hour) else (price_per_day / 24)
                
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

                product.update_available_quantity()
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

    owner = get_tenant_owner(request.user)

    # Получаем параметры фильтров
    status        = request.GET.get('status', '')        # open / closed / all
    date_range    = request.GET.get('date_range', '')    # today / week / month / all
    overdue_only  = request.GET.get('overdue', '')       # 1 = только просроченные
    amount_min    = request.GET.get('amount_min', '')    # минимальная сумма
    amount_max    = request.GET.get('amount_max', '')    # максимальная сумма
    sort_by       = request.GET.get('sort', '-created_at')  # сортировка

    # Базовый queryset — только заказы текущего тенанта
    orders = RentalOrder.objects.filter(client__owner=owner).select_related('client').prefetch_related('items')
    
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
    total_open   = RentalOrder.objects.filter(status='open', client__owner=owner).count()
    total_closed = RentalOrder.objects.filter(status='closed', client__owner=owner).count()

    # Просроченные
    overdue_count = 0
    for order in RentalOrder.objects.filter(status='open', client__owner=owner).prefetch_related('items'):
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

    import re

    def _distribution_amount_for_order(notes_text: str, order_id_int: int):
        if not notes_text:
            return None
        if 'Распределение:' in notes_text:
            for line in notes_text.split('\n'):
                pattern = rf'Заказ\s*#{order_id_int}\s*:\s*(\d+(?:[\.,]\d+)?)\s*сом'
                match = re.search(pattern, line)
                if match:
                    return float(match.group(1).replace(',', '.'))
        return None

    def _paid_for_order(client_obj, order_id_int: int) -> float:
        paid = 0.0
        for p in client_obj.payments.all():
            amt = _distribution_amount_for_order(p.notes or '', order_id_int)
            if amt is not None:
                paid += amt
                continue

            # Фолбэк для старых платежей без блока "Распределение"
            if p.notes and (f'Заказ #{order_id_int}' in p.notes or f'#{order_id_int}' in p.notes):
                # Если явно указан заказ в тексте — считаем весь платёж относящимся к нему
                paid += float(p.amount)
        return paid
    
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
                ).order_by('created_at')
            else:
                # Важно: распределяем не только по open, но и по closed, если там остался долг
                orders_to_pay = client.rental_orders.all().order_by('created_at')
            
            # Распределяем оплату
            remaining_payment = payment_amount
            payment_distribution = []
            paid_orders = []
            
            for order in orders_to_pay:
                if remaining_payment <= 0:
                    break

                already_paid = _paid_for_order(client, order.id)
                order_due = float(order.get_current_total()) - already_paid
                if order_due <= 0:
                    continue

                if remaining_payment >= order_due:
                    # Полностью оплачен
                    paid_amount = order_due
                    remaining_payment -= order_due
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

                # Если остался остаток — это аванс
                if remaining_payment > 0:
                    full_notes += f"\n\nАванс: {remaining_payment:.0f} сом"
            else:
                full_notes = notes if notes else 'Аванс (нет долгов по заказам)'
            
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
    owner = get_tenant_owner(request.user)
    clients = Client.objects.filter(owner=owner).order_by('last_name', 'first_name')
    
    # Клиенты с долгом
    clients_with_debt = []
    for client in clients:
        debt = client.get_debt()
        if debt > 0:
            open_orders = client.rental_orders.all().order_by('created_at')
            orders_list = []
            for order in open_orders:
                already_paid = _paid_for_order(client, order.id)
                order_due = float(order.get_current_total()) - already_paid
                if order_due <= 0:
                    continue
                orders_list.append({
                    'id': order.id,
                    'created_at': order.created_at,
                    'total': float(order.get_current_total()),
                    'due': order_due,
                    'status': order.status,
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
            for order in selected_client.rental_orders.all().order_by('created_at'):
                already_paid = _paid_for_order(selected_client, order.id)
                order_due = float(order.get_current_total()) - already_paid
                if order_due <= 0:
                    continue
                selected_client_orders.append({
                    'id': order.id,
                    'created_at': order.created_at,
                    'total': float(order.get_current_total()),
                    'due': order_due,
                    'status': order.status,
                    'items_count': order.items.count(),
                })
        except Client.DoesNotExist:
            pass
    
    clients_with_debt_ids = [d['client'].id for d in clients_with_debt]

    context = {
        'clients': clients,
        'clients_with_debt': clients_with_debt,
        'clients_with_debt_ids': clients_with_debt_ids,
        'selected_client': selected_client,
        'selected_client_id': selected_client_id,
        'selected_client_orders': selected_client_orders,
    }
    
    return render(request, 'rental/payment.html', context)


@login_required
def client_orders_json(request, client_id):
    """AJAX: вернуть список заказов клиента с суммами к оплате"""
    import json as _json
    client = get_object_or_404(Client, id=client_id)

    def _paid_for_order_local(client_obj, order_id_int):
        import re
        paid = 0.0
        for p in client_obj.payments.all():
            notes_text = p.notes or ''
            if 'Распределение:' in notes_text:
                for line in notes_text.split('\n'):
                    m = re.search(rf'Заказ\s*#{order_id_int}\s*:\s*(\d+(?:[\.,]\d+)?)\s*сом', line)
                    if m:
                        paid += float(m.group(1).replace(',', '.'))
                        break
            elif f'Заказ #{order_id_int}' in notes_text or f'#{order_id_int}' in notes_text:
                paid += float(p.amount)
        return paid

    orders_data = []
    for order in client.rental_orders.filter(status='open').order_by('created_at'):
        already_paid = _paid_for_order_local(client, order.id)
        due = float(order.get_current_total()) - already_paid
        if due <= 0:
            continue
        orders_data.append({
            'id': order.id,
            'created_at': order.created_at.strftime('%d.%m.%Y %H:%M'),
            'items_count': order.items.count(),
            'status': order.status,
            'status_display': 'открыт' if order.status == 'open' else 'закрыт',
            'due': round(due),
            'total': round(float(order.get_current_total())),
        })

    return JsonResponse({'orders': orders_data})


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
                            
                            # ✅ ВАЖНО: ОБНОВЛЯЕМ ДОСТУПНОСТЬ ТОВАРА
                            product = order_item.product
                            product.update_available_quantity()
                            
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
            
            messages.success(request, '✅ Товары возвращены и инвентарь обновлён!')
            return redirect('main:client_detail', client_id=client_id)
        else:
            return_doc.delete()
            messages.warning(request, '⚠️ Нет товаров для возврата')
            return redirect(f'/rental/returns/?client_id={client_id}')
    
    # GET запрос
    _returns_owner = get_tenant_owner(request.user)
    clients_with_orders = []

    for client in Client.objects.filter(owner=_returns_owner):
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

    owner = get_tenant_owner(request.user)
    selected_client_id = request.GET.get('client_id', '')
    clients = Client.objects.filter(owner=owner).order_by('last_name', 'first_name')

    if not selected_client_id:
        context = {
            'clients': clients,
            'selected_client': None,
            'order_groups': [],
        }
        return render(request, 'main/history.html', context)

    try:
        selected_client = Client.objects.get(id=selected_client_id, owner=owner)
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
        import re as _re
        _log_pattern = _re.compile(r'^\[\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\]')
        _local_now = timezone.localtime(timezone.now())
        _username = request.user.username

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
                        product.update_available_quantity()
                        # Log добавление товара
                        _log_line = (
                            f"[{_local_now.strftime('%d.%m.%Y %H:%M')}] "
                            f"{_username}: "
                            f"Добавил товар {product.name} x{quantity} на {days} дн {hours} ч ({int(total_cost)} сом)"
                        )
                        if order.notes:
                            order.notes += '\n' + _log_line
                        else:
                            order.notes = _log_line
                        order.save()
                        return redirect('main:edit_order', order_id=order.id)
                except Product.DoesNotExist:
                    pass
        
        # === ОБНОВЛЕНИЕ ПРИМЕЧАНИЙ ===
        # Сохраняем пользовательские заметки, сохраняя системные лог-строки
        _user_notes = request.POST.get('notes', '').strip()
        _system_log_lines = []
        if order.notes:
            for _line in order.notes.split('\n'):
                if _log_pattern.match(_line.strip()):
                    _system_log_lines.append(_line)
        _combined = _user_notes
        if _system_log_lines:
            if _combined:
                _combined += '\n\n'
            _combined += '\n'.join(_system_log_lines)
        order.notes = _combined
        order.save()

        # Список новых лог-записей для этого редактирования
        _edit_logs = []

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
                                _edit_logs.append(
                                    f"[{_local_now.strftime('%d.%m.%Y %H:%M')}] {_username}: "
                                    f"Изменил количество {order_item.product.name} с {old_quantity} на {new_quantity} шт"
                                )
                        else:
                            if difference != 0:
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
                            if difference != 0:
                                _edit_logs.append(
                                    f"[{_local_now.strftime('%d.%m.%Y %H:%M')}] {_username}: "
                                    f"Изменил количество {order_item.product.name} с {old_quantity} на {new_quantity} шт"
                                )
                
                except OrderItem.DoesNotExist:
                    pass
            
            # Обновление дней
            if key.startswith('item_days_'):
                item_id = key.replace('item_days_', '')
                new_days = int(request.POST.get(key, 0))
                
                try:
                    order_item = OrderItem.objects.get(id=item_id, order=order)
                    old_days = order_item.rental_days
                    order_item.rental_days = new_days
                    order_item.planned_return_date = order_item.issued_date + timedelta(days=new_days, hours=order_item.rental_hours)

                    # Пересчёт
                    total_rental_hours = (new_days * 24) + order_item.rental_hours
                    total_days_decimal = Decimal(total_rental_hours) / Decimal(24)
                    order_item.original_total_cost = order_item.price_per_day * total_days_decimal * Decimal(order_item.quantity_taken)
                    order_item.current_total_cost = order_item.original_total_cost

                    order_item.save()
                    if old_days != new_days:
                        _edit_logs.append(
                            f"[{_local_now.strftime('%d.%m.%Y %H:%M')}] {_username}: "
                            f"Изменил срок {order_item.product.name} с {old_days} дн на {new_days} дн"
                        )
                except OrderItem.DoesNotExist:
                    pass

            # Обновление часов
            if key.startswith('item_hours_'):
                item_id = key.replace('item_hours_', '')
                new_hours = int(request.POST.get(key, 0))
                
                try:
                    order_item = OrderItem.objects.get(id=item_id, order=order)
                    old_hours = order_item.rental_hours
                    order_item.rental_hours = new_hours
                    order_item.planned_return_date = order_item.issued_date + timedelta(days=order_item.rental_days, hours=new_hours)

                    # Пересчёт
                    total_rental_hours = (order_item.rental_days * 24) + new_hours
                    total_days_decimal = Decimal(total_rental_hours) / Decimal(24)
                    order_item.original_total_cost = order_item.price_per_day * total_days_decimal * Decimal(order_item.quantity_taken)
                    order_item.current_total_cost = order_item.original_total_cost

                    order_item.save()
                    if old_hours != new_hours:
                        _edit_logs.append(
                            f"[{_local_now.strftime('%d.%m.%Y %H:%M')}] {_username}: "
                            f"Изменил часы {order_item.product.name} с {old_hours} ч на {new_hours} ч"
                        )
                except OrderItem.DoesNotExist:
                    pass
        
        # === УДАЛЕНИЕ ТОВАРОВ ===
        for key in request.POST:
            if key.startswith('delete_item_'):
                item_id = key.replace('delete_item_', '')

                try:
                    order_item = OrderItem.objects.get(id=item_id, order=order)

                    if order_item.quantity_returned == 0:
                        _deleted_name = order_item.product.name
                        _deleted_qty = order_item.quantity_taken
                        order_item.product.quantity_available += order_item.quantity_taken
                        order_item.product.save()
                        order_item.delete()
                        _edit_logs.append(
                            f"[{_local_now.strftime('%d.%m.%Y %H:%M')}] {_username}: "
                            f"Удалил товар {_deleted_name} x{_deleted_qty} шт"
                        )

                except OrderItem.DoesNotExist:
                    pass

        # Сохраняем новые лог-записи в notes заказа
        if _edit_logs:
            _log_block = '\n'.join(_edit_logs)
            order.refresh_from_db()
            if order.notes:
                order.notes += '\n' + _log_block
            else:
                order.notes = _log_block
            order.save()

        return redirect('main:client_detail', client_id=order.client.id)
    
    # GET запрос
    import re as _re
    _log_pat = _re.compile(r'^\[\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\]')
    user_notes_display = ''
    if order.notes:
        non_system = [l for l in order.notes.split('\n') if not _log_pat.match(l.strip())]
        user_notes_display = '\n'.join(non_system).strip()

    _edit_owner = get_tenant_owner(request.user)
    available_products = Product.objects.filter(owner=_edit_owner, is_active=True, quantity_available__gt=0).order_by('name')

    context = {
        'order': order,
        'available_products': available_products,
        'user_notes_display': user_notes_display,
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
    import re

    if request.method != 'POST':
        return redirect('main:client_detail', client_id=get_object_or_404(RentalOrder, id=order_id).client.id)

    order = get_object_or_404(RentalOrder, id=order_id)

    if order.status != 'open':
        messages.warning(request, 'Заказ уже закрыт')
        return redirect('main:client_detail', client_id=order.client.id)

    client = order.client

    # === Проверяем долг по заказу перед закрытием ===
    # Текущая стоимость заказа (с учётом просрочек/изменений)
    current_cost = float(order.get_current_total())

    # Сколько уже оплачено по этому заказу (по распределениям в примечаниях платежей)
    total_paid_for_order = 0.0
    for payment in client.payments.all():
        if payment.notes and f'#{order.id}' in payment.notes:
            if 'Распределение:' in payment.notes:
                for line in payment.notes.split('\n'):
                    pattern = rf'Заказ\s*#{order.id}\s*:\s*(\d+(?:[\.,]\d+)?)\s*сом'
                    match = re.search(pattern, line)
                    if match:
                        total_paid_for_order += float(match.group(1).replace(',', '.'))
            else:
                # Старые платежи могли быть без блока "Распределение"
                # В этом случае считаем, что весь платёж относится к заказу
                total_paid_for_order += float(payment.amount)

    client_balance = client.get_wallet_balance()
    order_debt = float(calculate_order_debt(order, total_paid_for_order, client_balance))

    if order_debt > 0:
        messages.error(
            request,
            f'Нельзя закрыть заказ, пока есть долг по заказу: {order_debt:.0f} сом. '
            'Сначала примите оплату или зачтите аванс.'
        )
        return redirect('main:client_detail', client_id=client.id)

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
            
            # Обновляем OrderItem
            item.quantity_returned += item.quantity_remaining
            item.quantity_remaining = 0
            item.actual_cost = calculated_cost
            item.current_total_cost = calculated_cost
            item.save()
            
            # ✅ ОБНОВЛЯЕМ ИНВЕНТАРЬ
            product = item.product
            product.update_available_quantity()
    
    order.status = 'closed'
    order.save()
    
    messages.success(request, f'✅ Заказ #{order.id} закрыт. Все товары возвращены на склад.')
    return redirect('main:client_detail', client_id=order.client.id)


from django.db.models.functions import Lower

def global_search(request):
    """Глобальный поиск - фильтрация в Python (работает всегда!)"""

    query = request.GET.get('q', '').strip()

    print(f"Поиск: '{query}'")

    if len(query) < 2:
        return JsonResponse({
            'clients': [],
            'orders': [],
            'products': []
        })

    from apps.clients.models import Client
    from apps.rental.models import RentalOrder
    from apps.inventory.models import Product

    owner = get_tenant_owner(request.user)

    # Приводим к нижнему регистру для поиска
    query_lower = query.lower()

    # ============================================================
    # ПОИСК КЛИЕНТОВ В PYTHON
    # ============================================================

    # Получаем клиентов текущего тенанта
    all_clients = Client.objects.filter(owner=owner).prefetch_related('phones')
    
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
        found_orders = list(RentalOrder.objects.filter(id=order_id, client__owner=owner).select_related('client')[:5])
    except ValueError:
        # Иначе ищем по клиенту
        all_orders = RentalOrder.objects.filter(client__owner=owner).select_related('client').prefetch_related('client__phones')[:100]
        
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
    
    all_products = Product.objects.filter(owner=owner)
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

@login_required
def api_overdue_orders(request):
    """API: список просроченных открытых заказов для колокольчика"""
    now = timezone.now()
    owner = get_tenant_owner(request.user)
    overdue_items = []
    seen_orders = set()

    from apps.rental.models import OrderItem
    items = (OrderItem.objects
             .filter(order__status='open', order__client__owner=owner, quantity_remaining__gt=0, planned_return_date__lt=now)
             .select_related('order', 'order__client', 'product')
             .order_by('planned_return_date'))

    for item in items:
        order = item.order
        if order.id in seen_orders:
            continue
        seen_orders.add(order.id)

        # Collect all overdue products for this order
        overdue_products = (OrderItem.objects
                            .filter(order=order, quantity_remaining__gt=0, planned_return_date__lt=now)
                            .select_related('product'))
        products_str = ', '.join(
            f"{oi.product.name} x{oi.quantity_remaining}"
            for oi in overdue_products
        )
        earliest = overdue_products.order_by('planned_return_date').first()
        since_str = timezone.localtime(earliest.planned_return_date).strftime('%d.%m.%Y %H:%M') if earliest else ''

        overdue_items.append({
            'order_id': order.id,
            'client': order.client.get_full_name(),
            'products': products_str,
            'since': since_str,
            'url': f'/clients/{order.client.id}/',
        })

    return JsonResponse({
        'count': len(overdue_items),
        'orders': overdue_items,
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



@login_required
def edit_order_dates_with_log(request, order_id):
    """Изменить даты возврата с логированием в notes"""
    order = get_object_or_404(RentalOrder, id=order_id)
    
    if not request.user.is_staff:
        messages.error(request, '🔒 Нет прав')
        return redirect('main:client_detail', client_id=order.client.id)
    
    if request.method == 'POST':
        changes_log = []
        
        for item in order.items.all():
            new_date_str = request.POST.get(f'return_date_{item.id}')
            
            if new_date_str:
                try:
                    new_date = timezone.datetime.strptime(new_date_str, '%Y-%m-%dT%H:%M')
                    new_date = timezone.make_aware(new_date)
                except ValueError:
                    continue
                
                # Сравниваем без секунд (форма не отправляет секунды)
                if new_date == item.planned_return_date.replace(second=0, microsecond=0):
                    continue
                
                old_date = item.planned_return_date
                old_cost = item.original_total_cost
                
                # Пересчёт
                item.planned_return_date = new_date
                item.recalculate_from_dates()
                item.save()
                
                # Логируем изменение
                cost_diff = item.original_total_cost - old_cost
                local_now = timezone.localtime()
                log_entry = (
                    f"[{local_now.strftime('%d.%m.%Y %H:%M')}] "
                    f"{request.user.username}: "
                    f"Изменил дату возврата {item.product.name} x{item.quantity_taken} "
                    f"с {old_date.strftime('%d.%m.%Y %H:%M')} "
                    f"на {new_date.strftime('%d.%m.%Y %H:%M')} "
                    f"({cost_diff:+.0f} сом)"
                )
                changes_log.append(log_entry)
        
        if changes_log:
            # Добавляем в notes заказа
            if order.notes:
                order.notes += '\n\n' + '\n'.join(changes_log)
            else:
                order.notes = '\n'.join(changes_log)
            order.save()
            
            messages.success(request, '✅ Даты обновлены и записаны в историю заказа')
        else:
            messages.info(request, 'ℹ️ Изменений не было')
        
        return redirect('main:client_detail', client_id=order.client.id)
    
    context = {
        'order': order,
        'client': order.client,
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

    owner = get_tenant_owner(request.user)

    # Получаем выбранного клиента
    selected_client_id = request.GET.get('client_id')
    selected_client_id_int = int(selected_client_id) if selected_client_id else None

    # Базовый запрос - активные заказы текущего тенанта
    orders = RentalOrder.objects.filter(
        status='open', client__owner=owner
    ).select_related('client').prefetch_related('items__product', 'client__phones')

    # Фильтрация по клиенту
    if selected_client_id_int:
        orders = orders.filter(client_id=selected_client_id_int)

    # Получаем список клиентов текущего тенанта для выпадающего списка
    clients = Client.objects.filter(
        owner=owner,
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

    referer = request.META.get('HTTP_REFERER', '')
    if 'superadmin' in referer:
        return redirect('main:superuser_panel')
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


def superuser_required(view_func):
    """Декоратор — только суперпользователь"""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not request.user.is_superuser:
            messages.error(request, '🔒 Доступ только для создателя системы.')
            return redirect('main:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@superuser_required
def superuser_panel(request):
    """Панель суперадминистратора — только для создателя системы"""
    from apps.rental.models import RentalOrder
    from apps.clients.models import Client

    # Пользователи, ожидающие одобрения
    pending_users = User.objects.filter(is_active=False).order_by('date_joined')

    # Одобрение пользователя через POST
    if request.method == 'POST':
        action = request.POST.get('action')
        uid = request.POST.get('user_id')
        target = get_object_or_404(User, id=uid)
        if action == 'approve':
            # Новый пользователь становится суперадмином своей компании
            target.is_active = True
            target.is_staff = False   # не системный создатель
            target.is_superuser = True  # владелец своей компании
            target.save()
            admin_group, _ = Group.objects.get_or_create(name='Администратор')
            target.groups.add(admin_group)
            # Убеждаемся что профиль есть и owner=None (владелец своей компании)
            UserProfile.objects.get_or_create(user=target, defaults={'owner': None})
            messages.success(request, f'✅ Пользователь «{target.username}» одобрен. Теперь у него своя пустая CRM.')
        elif action == 'reject':
            target.delete()
            messages.success(request, f'🗑 Пользователь «{target.username}» удалён.')
        return redirect('main:superuser_panel')

    # Superuser panel always shows system-wide totals (all tenants)
    stats = {
        'total_users':   User.objects.count(),
        'pending_users': pending_users.count(),
        'total_clients': Client.objects.count(),   # system-wide
        'open_orders':   RentalOrder.objects.filter(status='open').count(),  # system-wide
    }

    return render(request, 'main/superuser_panel.html', {
        'pending_users': pending_users,
        'stats': stats,
        'all_users': User.objects.order_by('-date_joined')[:20],
    })
