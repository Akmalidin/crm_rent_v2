
import requests
from django.utils import timezone
from datetime import timedelta
import json

# Простое хранилище состояний администратора (chat_id -> dict)
_admin_states = {}


# ============================================================
# БАЗОВЫЕ ФУНКЦИИ
# ============================================================

def send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=None):
    """Отправить сообщение с кнопками"""
    from django.conf import settings

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token or not chat_id:
        return False

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    data = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode,
    }

    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)

    try:
        response = requests.post(url, data=data, timeout=10)
        return response.json().get('ok', False)
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def answer_callback_query(callback_query_id, text=None):
    """Ответить на нажатие кнопки"""
    from django.conf import settings

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        return False

    url = f'https://api.telegram.org/bot{token}/answerCallbackQuery'
    data = {'callback_query_id': callback_query_id}
    if text:
        data['text'] = text

    try:
        requests.post(url, data=data, timeout=5)
        return True
    except:
        return False


# ============================================================
# ОПРЕДЕЛЕНИЕ РОЛЕЙ
# ============================================================

def is_creator(chat_id):
    """Создатель системы (суперадмин)"""
    from django.conf import settings
    admin_id = str(getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', ''))
    return bool(admin_id) and str(chat_id) == admin_id


# Обратная совместимость
def is_admin(chat_id):
    return is_creator(chat_id)


def get_director_profile(chat_id):
    """Найти профиль директора по telegram_chat_id. Возвращает UserProfile или None."""
    from apps.main.models import UserProfile
    return UserProfile.objects.filter(
        telegram_chat_id=str(chat_id),
        role='director',
    ).select_related('user').first()


def notify_director(director_user, text, reply_markup=None):
    """Отправить уведомление директору если у него привязан Telegram."""
    try:
        profile = director_user.profile
        if profile.telegram_chat_id:
            send_telegram_message(profile.telegram_chat_id, text, reply_markup=reply_markup)
    except Exception:
        pass


# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def get_client_keyboard():
    return {
        'inline_keyboard': [
            [
                {'text': '💰 Мой баланс', 'callback_data': 'balance'},
                {'text': '📦 Мои заказы', 'callback_data': 'orders'},
            ],
            [
                {'text': '📞 Контакты', 'callback_data': 'contact'},
                {'text': '❓ Помощь', 'callback_data': 'help'},
            ],
        ]
    }


def get_admin_keyboard():
    return {
        'inline_keyboard': [
            [
                {'text': '📊 Отчёт за сегодня', 'callback_data': 'admin_report_today'},
                {'text': '📈 Отчёт за неделю', 'callback_data': 'admin_report_week'},
            ],
            [
                {'text': '⚠️ Просроченные', 'callback_data': 'admin_overdue'},
                {'text': '💰 Должники', 'callback_data': 'admin_debtors'},
            ],
            [
                {'text': '📦 Активные заказы', 'callback_data': 'admin_active'},
                {'text': '👥 Новые клиенты', 'callback_data': 'admin_new_clients'},
            ],
            [
                {'text': '🔄 Обновить', 'callback_data': 'admin_menu'},
            ],
        ]
    }


def get_director_keyboard():
    """Меню директора — видит только своих клиентов/заказы"""
    return {
        'inline_keyboard': [
            [
                {'text': '📊 Мой отчёт сегодня', 'callback_data': 'dir_report_today'},
                {'text': '📈 Отчёт за неделю', 'callback_data': 'dir_report_week'},
            ],
            [
                {'text': '⚠️ Просроченные', 'callback_data': 'dir_overdue'},
                {'text': '💰 Должники', 'callback_data': 'dir_debtors'},
            ],
            [
                {'text': '📦 Активные заказы', 'callback_data': 'dir_active'},
                {'text': '👥 Новые клиенты', 'callback_data': 'dir_new_clients'},
            ],
            [
                {'text': '📢 Рассылка клиентам', 'callback_data': 'dir_broadcast_menu'},
                {'text': '🔄 Обновить', 'callback_data': 'dir_menu'},
            ],
        ]
    }


def get_back_button():
    return {
        'inline_keyboard': [
            [{'text': '« Назад в меню', 'callback_data': 'back_to_menu'}],
        ]
    }


def get_broadcast_menu_keyboard():
    return {
        'inline_keyboard': [
            [{'text': '📢 Уведомить просроченных', 'callback_data': 'broadcast_overdue'}],
            [{'text': '💸 Уведомить должников',   'callback_data': 'broadcast_debt'}],
            [{'text': '✍️ Написать своё сообщение', 'callback_data': 'broadcast_custom_start'}],
            [{'text': '« Назад в меню',            'callback_data': 'back_to_menu'}],
        ]
    }


def get_dir_broadcast_menu_keyboard():
    return {
        'inline_keyboard': [
            [{'text': '📢 Уведомить просроченных', 'callback_data': 'dir_broadcast_overdue'}],
            [{'text': '💸 Уведомить должников',   'callback_data': 'dir_broadcast_debt'}],
            [{'text': '✍️ Написать своё сообщение', 'callback_data': 'dir_broadcast_custom_start'}],
            [{'text': '« Назад в меню',            'callback_data': 'back_to_menu'}],
        ]
    }


def get_broadcast_target_keyboard(prefix=''):
    return {
        'inline_keyboard': [
            [{'text': '👥 Всем клиентам',  'callback_data': f'{prefix}send_custom_all'}],
            [{'text': '⚠️ Просроченным',   'callback_data': f'{prefix}send_custom_overdue'}],
            [{'text': '💸 Должникам',      'callback_data': f'{prefix}send_custom_debtors'}],
            [{'text': '❌ Отмена',         'callback_data': 'back_to_menu'}],
        ]
    }


def get_client_reply_keyboard():
    return {
        'keyboard': [
            [{'text': '💰 Мой баланс'}, {'text': '📦 Мои заказы'}],
            [{'text': '📞 Контакты'},   {'text': '❓ Помощь'}],
        ],
        'resize_keyboard': True,
        'persistent': True,
    }


def get_admin_reply_keyboard():
    return {
        'keyboard': [
            [{'text': '📊 Отчёт сегодня'}, {'text': '📈 Отчёт за неделю'}],
            [{'text': '⚠️ Просроченные'},  {'text': '💰 Должники'}],
            [{'text': '📦 Активные заказы'}, {'text': '👥 Новые клиенты'}],
            [{'text': '📢 Рассылка'}],
        ],
        'resize_keyboard': True,
        'persistent': True,
    }


def get_director_reply_keyboard():
    return {
        'keyboard': [
            [{'text': '📊 Мой отчёт'}, {'text': '⚠️ Просроченные'}],
            [{'text': '💰 Должники'}, {'text': '📦 Активные заказы'}],
            [{'text': '📢 Рассылка клиентам'}],
        ],
        'resize_keyboard': True,
        'persistent': True,
    }


# ============================================================
# ОТЧЁТЫ — СОЗДАТЕЛЬ (видит всё)
# ============================================================

def admin_report_today():
    from apps.clients.models import Client
    from apps.rental.models import RentalOrder, Payment

    now = timezone.now()
    today = now.date()
    orders_today = RentalOrder.objects.filter(created_at__date=today)
    payments_today = Payment.objects.filter(payment_date__date=today)
    new_clients = Client.objects.filter(created_at__date=today).count()

    return f"""📊 <b>Отчёт за сегодня</b> ({today.strftime('%d.%m.%Y')})

📦 <b>Заказы:</b> {orders_today.count()} шт на {int(sum(float(o.get_current_total()) for o in orders_today)):,} сом
💰 <b>Оплаты:</b> {payments_today.count()} шт на {int(sum(float(p.amount) for p in payments_today)):,} сом
👥 <b>Новые клиенты:</b> {new_clients} чел

<i>CRM Аренда</i>""".replace(',', ' ')


def admin_report_week():
    from apps.clients.models import Client
    from apps.rental.models import RentalOrder, Payment

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    orders_week = RentalOrder.objects.filter(created_at__gte=week_ago)
    payments_week = Payment.objects.filter(payment_date__gte=week_ago)
    new_clients = Client.objects.filter(created_at__gte=week_ago).count()

    return f"""📈 <b>Отчёт за неделю</b>

📦 <b>Заказов:</b> {orders_week.count()} на {int(sum(float(o.get_current_total()) for o in orders_week)):,} сом
💰 <b>Оплат:</b> {int(sum(float(p.amount) for p in payments_week)):,} сом
👥 <b>Новых клиентов:</b> {new_clients}

<i>{week_ago.strftime('%d.%m')} - {now.strftime('%d.%m.%Y')}</i>""".replace(',', ' ')


def admin_overdue_orders():
    from apps.rental.models import RentalOrder

    now = timezone.now()
    overdue = []
    for order in RentalOrder.objects.filter(status='open').prefetch_related('items__product', 'client__phones'):
        overdue_items = [i for i in order.items.all() if i.quantity_remaining > 0 and i.planned_return_date < now]
        if overdue_items:
            days = (now - min(i.planned_return_date for i in overdue_items)).days
            overdue.append((order, days))

    if not overdue:
        return "✅ <b>Просроченных заказов нет!</b>"

    overdue.sort(key=lambda x: x[1], reverse=True)
    text = f"⚠️ <b>Просроченные заказы ({len(overdue)}):</b>\n\n"
    for order, days in overdue[:10]:
        phones = ', '.join([p.phone_number for p in order.client.phones.all()])
        text += f"📦 <b>Заказ #{order.id}</b> — {days} дн.\n👤 {order.client.get_full_name()}\n📞 {phones}\n💰 {int(order.get_current_total()):,} сом\n\n".replace(',', ' ')
    return text


def admin_debtors():
    from apps.clients.models import Client

    debtors = [(c, abs(float(c.get_wallet_balance()))) for c in Client.objects.prefetch_related('phones') if float(c.get_wallet_balance()) < 0]
    if not debtors:
        return "✅ <b>Должников нет!</b>"

    debtors.sort(key=lambda x: x[1], reverse=True)
    text = f"💰 <b>Должники ({len(debtors)}):</b>\n\n"
    for client, debt in debtors[:10]:
        phones = ', '.join([p.phone_number for p in client.phones.all()])
        text += f"👤 <b>{client.get_full_name()}</b>\n📞 {phones}\n💸 Долг: <b>{int(debt):,} сом</b>\n\n".replace(',', ' ')
    return text


def admin_active_orders():
    from apps.rental.models import RentalOrder

    orders = RentalOrder.objects.filter(status='open').select_related('client').prefetch_related('client__phones')[:15]
    if not orders:
        return "📭 <b>Нет активных заказов</b>"

    text = f"📦 <b>Активные заказы ({orders.count()}):</b>\n\n"
    for order in orders:
        phones = ', '.join([p.phone_number for p in order.client.phones.all()])
        text += f"📦 <b>#{order.id}</b> — {order.client.get_full_name()}\n📞 {phones}\n💰 {int(order.get_current_total()):,} сом\n📅 {order.created_at.strftime('%d.%m.%Y')}\n\n".replace(',', ' ')
    return text


def admin_new_clients():
    from apps.clients.models import Client

    week_ago = timezone.now() - timedelta(days=7)
    clients = Client.objects.filter(created_at__gte=week_ago).order_by('-created_at').prefetch_related('phones')[:10]
    if not clients:
        return "📭 <b>Новых клиентов нет</b>"

    text = f"👥 <b>Новые клиенты за неделю ({clients.count()}):</b>\n\n"
    for client in clients:
        phones = ', '.join([p.phone_number for p in client.phones.all()])
        text += f"👤 <b>{client.get_full_name()}</b>\n📞 {phones}\n📅 {client.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    return text


# ============================================================
# ОТЧЁТЫ — ДИРЕКТОР (видит только своих клиентов/заказы)
# ============================================================

def _dir_owner(director_profile):
    """Возвращает user-объект владельца тенанта директора"""
    return director_profile.user


def director_report_today(director_profile):
    from apps.clients.models import Client
    from apps.rental.models import RentalOrder, Payment

    owner = _dir_owner(director_profile)
    now = timezone.now()
    today = now.date()

    orders_today = RentalOrder.objects.filter(created_at__date=today, owner=owner)
    payments_today = Payment.objects.filter(payment_date__date=today, order__owner=owner)
    new_clients = Client.objects.filter(created_at__date=today, owner=owner).count()

    return f"""📊 <b>Мой отчёт за сегодня</b> ({today.strftime('%d.%m.%Y')})

📦 <b>Заказы:</b> {orders_today.count()} шт на {int(sum(float(o.get_current_total()) for o in orders_today)):,} сом
💰 <b>Оплаты:</b> {payments_today.count()} шт на {int(sum(float(p.amount) for p in payments_today)):,} сом
👥 <b>Новые клиенты:</b> {new_clients} чел""".replace(',', ' ')


def director_report_week(director_profile):
    from apps.clients.models import Client
    from apps.rental.models import RentalOrder, Payment

    owner = _dir_owner(director_profile)
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    orders_week = RentalOrder.objects.filter(created_at__gte=week_ago, owner=owner)
    payments_week = Payment.objects.filter(payment_date__gte=week_ago, order__owner=owner)
    new_clients = Client.objects.filter(created_at__gte=week_ago, owner=owner).count()

    return f"""📈 <b>Мой отчёт за неделю</b>

📦 <b>Заказов:</b> {orders_week.count()} на {int(sum(float(o.get_current_total()) for o in orders_week)):,} сом
💰 <b>Оплат:</b> {int(sum(float(p.amount) for p in payments_week)):,} сом
👥 <b>Новых клиентов:</b> {new_clients}

<i>{week_ago.strftime('%d.%m')} - {now.strftime('%d.%m.%Y')}</i>""".replace(',', ' ')


def director_overdue_orders(director_profile):
    from apps.rental.models import RentalOrder

    owner = _dir_owner(director_profile)
    now = timezone.now()
    overdue = []
    for order in RentalOrder.objects.filter(status='open', owner=owner).prefetch_related('items__product', 'client__phones'):
        overdue_items = [i for i in order.items.all() if i.quantity_remaining > 0 and i.planned_return_date < now]
        if overdue_items:
            days = (now - min(i.planned_return_date for i in overdue_items)).days
            overdue.append((order, days))

    if not overdue:
        return "✅ <b>Просроченных заказов нет!</b>"

    overdue.sort(key=lambda x: x[1], reverse=True)
    text = f"⚠️ <b>Просроченные заказы ({len(overdue)}):</b>\n\n"
    for order, days in overdue[:10]:
        phones = ', '.join([p.phone_number for p in order.client.phones.all()])
        text += f"📦 <b>Заказ #{order.id}</b> — {days} дн.\n👤 {order.client.get_full_name()}\n📞 {phones}\n\n"
    return text


def director_debtors(director_profile):
    from apps.clients.models import Client

    owner = _dir_owner(director_profile)
    debtors = [(c, abs(float(c.get_wallet_balance()))) for c in Client.objects.filter(owner=owner).prefetch_related('phones') if float(c.get_wallet_balance()) < 0]
    if not debtors:
        return "✅ <b>Должников нет!</b>"

    debtors.sort(key=lambda x: x[1], reverse=True)
    text = f"💰 <b>Должники ({len(debtors)}):</b>\n\n"
    for client, debt in debtors[:10]:
        phones = ', '.join([p.phone_number for p in client.phones.all()])
        text += f"👤 <b>{client.get_full_name()}</b>\n📞 {phones}\n💸 Долг: <b>{int(debt):,} сом</b>\n\n".replace(',', ' ')
    return text


def director_active_orders(director_profile):
    from apps.rental.models import RentalOrder

    owner = _dir_owner(director_profile)
    orders = RentalOrder.objects.filter(status='open', owner=owner).select_related('client').prefetch_related('client__phones')[:15]
    if not orders:
        return "📭 <b>Нет активных заказов</b>"

    text = f"📦 <b>Активные заказы ({orders.count()}):</b>\n\n"
    for order in orders:
        phones = ', '.join([p.phone_number for p in order.client.phones.all()])
        text += f"📦 <b>#{order.id}</b> — {order.client.get_full_name()}\n📞 {phones}\n💰 {int(order.get_current_total()):,} сом\n\n".replace(',', ' ')
    return text


def director_new_clients(director_profile):
    from apps.clients.models import Client

    owner = _dir_owner(director_profile)
    week_ago = timezone.now() - timedelta(days=7)
    clients = Client.objects.filter(created_at__gte=week_ago, owner=owner).order_by('-created_at').prefetch_related('phones')[:10]
    if not clients:
        return "📭 <b>Новых клиентов нет</b>"

    text = f"👥 <b>Новые клиенты за неделю ({clients.count()}):</b>\n\n"
    for client in clients:
        phones = ', '.join([p.phone_number for p in client.phones.all()])
        text += f"👤 <b>{client.get_full_name()}</b>\n📞 {phones}\n📅 {client.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    return text


# ============================================================
# КЛИЕНТСКИЕ ОБРАБОТЧИКИ
# ============================================================

def handle_balance(chat_id):
    from apps.clients.models import Client

    client = Client.objects.filter(telegram_id=chat_id).first()
    if not client:
        send_telegram_message(chat_id,
            "❌ Вы не зарегистрированы.\nСообщите менеджеру ваш ID: <code>" + str(chat_id) + "</code>",
            reply_markup=get_back_button())
        return

    balance = float(client.get_wallet_balance())
    paid = float(client.get_total_paid())
    debt = float(client.get_total_debt())
    emoji = "✅" if balance >= 0 else "⚠️"
    balance_text = f"+{int(balance):,}" if balance > 0 else f"{int(balance):,}"

    text = f"""{emoji} <b>Ваш баланс</b>

👤 {client.get_full_name()}

💰 Всего оплачено: {int(paid):,} сом
💸 Общий долг: {int(debt):,} сом
💳 Баланс: <b>{balance_text} сом</b>

{'✅ Задолженности нет' if balance >= 0 else '⚠️ Пожалуйста, погасите задолженность'}"""

    send_telegram_message(chat_id, text.replace(',', ' '), reply_markup=get_back_button())


def handle_orders(chat_id):
    from apps.clients.models import Client

    client = Client.objects.filter(telegram_id=chat_id).first()
    if not client:
        send_telegram_message(chat_id, "❌ Вы не зарегистрированы.", reply_markup=get_back_button())
        return

    orders = client.rental_orders.filter(status='open').prefetch_related('items__product')
    if not orders:
        send_telegram_message(chat_id, "📭 У вас нет активных заказов.", reply_markup=get_back_button())
        return

    now = timezone.now()
    text = f"📦 <b>Ваши активные заказы ({orders.count()}):</b>\n\n"
    for order in orders:
        text += f"<b>Заказ #{order.id}</b> от {order.created_at.strftime('%d.%m.%Y')}\n"
        for item in order.items.all():
            if item.quantity_remaining > 0:
                is_overdue = item.planned_return_date < now
                status = "⚠️ ПРОСРОЧЕН" if is_overdue else f"до {item.planned_return_date.strftime('%d.%m.%Y')}"
                text += f"  • {item.product.name} — {item.quantity_remaining} шт ({status})\n"
        text += f"💰 Стоимость: {int(order.get_current_total()):,} сом\n\n".replace(',', ' ')

    send_telegram_message(chat_id, text, reply_markup=get_back_button())


def handle_contact(chat_id):
    text = """📞 <b>Контакты</b>

🏢 <b>CRM Аренда Инструментов</b>

📱 Телефон: +996-553-565-674
📧 Email: akmalmadakimov@gmail.com
🕐 Время работы: Пн-Вс 9:00-18:00

📍 Адрес: г. Ош, ул. Примерная 13

💬 Напишите нам в любое время!"""
    send_telegram_message(chat_id, text, reply_markup=get_back_button())


def handle_help(chat_id):
    text = """❓ <b>Помощь</b>

<b>Доступные команды:</b>

/start - Главное меню
/balance - Проверить баланс
/orders - Мои заказы
/contact - Контакты
/myid - Узнать ваш Telegram ID
/help - Эта справка"""
    send_telegram_message(chat_id, text, reply_markup=get_back_button())


# ============================================================
# РАССЫЛКА — СОЗДАТЕЛЬ
# ============================================================

def handle_broadcast_overdue(admin_chat_id):
    from apps.rental.models import RentalOrder

    sent, skipped, seen = 0, 0, set()
    for order in RentalOrder.objects.filter(status='open').prefetch_related('items', 'client'):
        if order.client_id in seen:
            continue
        if any(it.is_overdue for it in order.items.all()):
            ok = notify_overdue(order)
            seen.add(order.client_id)
            if ok:
                sent += 1
            else:
                skipped += 1

    send_telegram_message(admin_chat_id,
        f"✅ <b>Рассылка о просрочке завершена</b>\n\n📤 Отправлено: <b>{sent}</b>\n🚫 Без Telegram: <b>{skipped}</b>",
        reply_markup=get_admin_keyboard())


def handle_broadcast_debt(admin_chat_id):
    from apps.clients.models import Client

    sent, skipped = 0, 0
    for client in Client.objects.all():
        ok = notify_debt_reminder(client)
        if ok:
            sent += 1
        elif client.has_debt() and not client.telegram_id:
            skipped += 1

    send_telegram_message(admin_chat_id,
        f"✅ <b>Рассылка о долге завершена</b>\n\n📤 Отправлено: <b>{sent}</b>\n🚫 Без Telegram: <b>{skipped}</b>",
        reply_markup=get_admin_keyboard())


# ============================================================
# РАССЫЛКА — ДИРЕКТОР (только своим клиентам)
# ============================================================

def handle_dir_broadcast_overdue(director_chat_id, director_profile):
    from apps.rental.models import RentalOrder

    owner = _dir_owner(director_profile)
    sent, skipped, seen = 0, 0, set()
    for order in RentalOrder.objects.filter(status='open', owner=owner).prefetch_related('items', 'client'):
        if order.client_id in seen:
            continue
        if any(it.is_overdue for it in order.items.all()):
            ok = notify_overdue(order)
            seen.add(order.client_id)
            if ok:
                sent += 1
            else:
                skipped += 1

    send_telegram_message(director_chat_id,
        f"✅ <b>Рассылка о просрочке завершена</b>\n\n📤 Отправлено: <b>{sent}</b>\n🚫 Без Telegram: <b>{skipped}</b>",
        reply_markup=get_director_keyboard())


def handle_dir_broadcast_debt(director_chat_id, director_profile):
    from apps.clients.models import Client

    owner = _dir_owner(director_profile)
    sent, skipped = 0, 0
    for client in Client.objects.filter(owner=owner):
        ok = notify_debt_reminder(client)
        if ok:
            sent += 1
        elif client.has_debt() and not client.telegram_id:
            skipped += 1

    send_telegram_message(director_chat_id,
        f"✅ <b>Рассылка о долге завершена</b>\n\n📤 Отправлено: <b>{sent}</b>\n🚫 Без Telegram: <b>{skipped}</b>",
        reply_markup=get_director_keyboard())


# ============================================================
# УВЕДОМЛЕНИЯ КЛИЕНТАМ
# ============================================================

def _get_staff_telegram_ids():
    """Возвращает set telegram_chat_id всех директоров/сотрудников — чтобы не слать им клиентскую рассылку."""
    from apps.main.models import UserProfile
    ids = set(
        UserProfile.objects.exclude(telegram_chat_id='')
        .values_list('telegram_chat_id', flat=True)
    )
    # Также добавить ID создателя
    creator_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)
    if creator_id:
        ids.add(str(creator_id))
    return ids


def notify_overdue(order):
    client = order.client
    if not client.telegram_id:
        return False
    if str(client.telegram_id) in _get_staff_telegram_ids():
        return False

    now = timezone.now()
    overdue_items = [i for i in order.items.all() if i.quantity_remaining > 0 and i.planned_return_date < now]
    if not overdue_items:
        return False

    days_overdue = (now - min(i.planned_return_date for i in overdue_items)).days
    text = f"""⚠️ <b>Просрочка по заказу #{order.id}</b>

Уважаемый {client.get_full_name()},

По вашему заказу есть просроченные позиции.
Просрочка: <b>{days_overdue} дн.</b>

Пожалуйста, верните инструмент или свяжитесь с нами.

💰 Текущая сумма: <b>{int(client.get_wallet_balance()):,} сом</b>""".replace(',', ' ')

    return send_telegram_message(client.telegram_id, text)


def notify_debt_reminder(client):
    if not client.telegram_id:
        return False
    if str(client.telegram_id) in _get_staff_telegram_ids():
        return False
    debt = float(client.get_debt()) if hasattr(client, 'get_debt') else abs(float(client.get_wallet_balance()))
    if debt <= 0:
        return False
    text = (
        f"💰 <b>Напоминание о задолженности</b>\n\n"
        f"Уважаемый {client.get_full_name()},\n\n"
        f"У вас есть задолженность: <b>{int(debt):,} сом</b>\n\n"
        f"Пожалуйста, погасите долг при следующем визите или свяжитесь с нами."
    ).replace(',', ' ')
    return send_telegram_message(client.telegram_id, text)


def send_custom_broadcast(telegram_ids, message):
    sent, failed = 0, 0
    for chat_id in telegram_ids:
        ok = send_telegram_message(chat_id, message, parse_mode='HTML')
        if ok:
            sent += 1
        else:
            failed += 1
    return sent, failed


# ============================================================
# УВЕДОМЛЕНИЯ ДИРЕКТОРУ (вызываются из views.py)
# ============================================================

def notify_director_new_order(order):
    """Уведомить директора о новом заказе"""
    try:
        owner = order.owner
        profile = owner.profile
        if not profile.telegram_chat_id:
            return
        items_text = '\n'.join(
            f"  • {item.product.name} — {item.quantity} шт"
            for item in order.items.all()
        )
        text = f"""📦 <b>Новый заказ #{order.id}</b>

👤 Клиент: {order.client.get_full_name()}
📱 Телефон: {', '.join(p.phone_number for p in order.client.phones.all())}

<b>Товары:</b>
{items_text}

💰 Сумма: <b>{int(order.get_current_total()):,} сом</b>
📅 Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}""".replace(',', ' ')
        send_telegram_message(profile.telegram_chat_id, text)
    except Exception:
        pass


def notify_director_payment(payment):
    """Уведомить директора о принятой оплате"""
    try:
        owner = payment.client.owner
        if not owner:
            return
        profile = owner.profile
        if not profile.telegram_chat_id:
            return
        name = payment.client.get_full_name()
        amount = int(payment.amount)
        date_str = payment.payment_date.strftime("%d.%m.%Y %H:%M")
        text = (
            "<b>Принята оплата</b>" + chr(10) + chr(10) +
            "Клиент: " + name + chr(10) +
            "Сумма: <b>" + str(amount) + " сом</b>" + chr(10) +
            "Дата: " + date_str
        )
        send_telegram_message(profile.telegram_chat_id, text)
    except Exception:
        pass

def _handle_custom_broadcast_send(chat_id, data, role, director_profile=None):
    state = _admin_states.pop(str(chat_id), {})
    custom_text = state.get('text', '')
    if not custom_text:
        send_telegram_message(chat_id, 'Текст не найден. Начните заново.')
        return

    from apps.clients.models import Client
    from apps.rental.models import RentalOrder

    send_telegram_message(chat_id, 'Рассылка запущена...')

    if role == 'director' and director_profile:
        from apps.main.telegram_bot_complete import _dir_owner
        owner = _dir_owner(director_profile)
        base_qs = Client.objects.filter(owner=owner)
        prefix = 'dir_'
    else:
        base_qs = Client.objects.all()
        prefix = ''

    key = data.replace(prefix, '')

    if key == 'send_custom_all':
        chat_ids = list(base_qs.exclude(telegram_id__isnull=True).exclude(telegram_id='').values_list('telegram_id', flat=True))
    elif key == 'send_custom_overdue':
        overdue_ids = set()
        qs = RentalOrder.objects.filter(status='open')
        if role == 'director' and director_profile:
            from apps.main.telegram_bot_complete import _dir_owner
            qs = qs.filter(owner=_dir_owner(director_profile))
        for order in qs.prefetch_related('items'):
            if any(it.is_overdue for it in order.items.all()):
                overdue_ids.add(order.client_id)
        chat_ids = list(base_qs.filter(id__in=overdue_ids).exclude(telegram_id__isnull=True).exclude(telegram_id='').values_list('telegram_id', flat=True))
    else:
        chat_ids = [c.telegram_id for c in base_qs.exclude(telegram_id__isnull=True).exclude(telegram_id='') if float(c.get_wallet_balance()) < 0]

    staff_ids = _get_staff_telegram_ids()
    chat_ids = [cid for cid in chat_ids if str(cid) not in staff_ids]

    from apps.main.telegram_bot_complete import send_custom_broadcast, get_director_keyboard, get_admin_keyboard
    sent, failed = send_custom_broadcast(chat_ids, custom_text)
    kb = get_director_keyboard() if role == 'director' else get_admin_keyboard()
    send_telegram_message(
        chat_id,
        '<b>Рассылка завершена</b>' + chr(10) + chr(10) + 'Отправлено: <b>' + str(sent) + '</b>' + chr(10) + 'Ошибок: <b>' + str(failed) + '</b>',
        reply_markup=kb
    )
