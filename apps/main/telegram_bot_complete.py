
import requests
from django.utils import timezone
from datetime import timedelta
import json


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
# КЛАВИАТУРЫ (INLINE КНОПКИ)
# ============================================================

def get_client_keyboard():
    """Главное меню клиента"""
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
    """Главное меню администратора"""
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


def get_back_button():
    """Кнопка назад"""
    return {
        'inline_keyboard': [
            [{'text': '« Назад в меню', 'callback_data': 'back_to_menu'}],
        ]
    }


# ============================================================
# ОБРАБОТЧИКИ КОМАНД ДЛЯ КЛИЕНТОВ
# ============================================================

def handle_balance(chat_id):
    """Показать баланс клиента"""
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
    """Показать заказы клиента"""
    from apps.clients.models import Client
    
    client = Client.objects.filter(telegram_id=chat_id).first()
    
    if not client:
        send_telegram_message(chat_id,
            "❌ Вы не зарегистрированы.",
            reply_markup=get_back_button())
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
    """Показать контакты"""
    text = """📞 <b>Контакты</b>

🏢 <b>CRM Аренда Инструментов</b>

📱 Телефон: +996-553-565-674
📧 Email: akmalmadakimov@gmail.com
🕐 Время работы: Пн-Вс 9:00-18:00

📍 Адрес: г. Ош, ул. Примерная 13

💬 Напишите нам в любое время!"""
    
    send_telegram_message(chat_id, text, reply_markup=get_back_button())


def handle_help(chat_id):
    """Помощь"""
    text = """❓ <b>Помощь</b>

<b>Доступные команды:</b>

/start - Главное меню
/balance - Проверить баланс
/orders - Мои заказы
/contact - Контакты
/help - Эта справка

<b>Кнопки меню:</b>
💰 Мой баланс - проверка баланса и долга
📦 Мои заказы - список активных заказов
📞 Контакты - наши контакты
❓ Помощь - эта справка

<b>Уведомления:</b>
Вы будете получать автоматические уведомления:
• ⚠️ При просрочке возврата
• 📅 За день до срока возврата
• ✅ При подтверждении оплаты
• 💰 Напоминания о долге"""
    
    send_telegram_message(chat_id, text, reply_markup=get_back_button())


# ============================================================
# ОБРАБОТЧИКИ КОМАНД ДЛЯ АДМИНИСТРАТОРА
# ============================================================

def is_admin(chat_id):
    """Проверка что это админ"""
    from django.conf import settings
    admin_id = str(getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', ''))
    return str(chat_id) == admin_id


def admin_report_today():
    """Отчёт за сегодня"""
    from apps.clients.models import Client
    from apps.rental.models import RentalOrder, Payment
    
    now = timezone.now()
    today = now.date()
    
    orders_today = RentalOrder.objects.filter(created_at__date=today)
    orders_count = orders_today.count()
    orders_sum = sum(float(o.get_current_total()) for o in orders_today)
    
    payments_today = Payment.objects.filter(payment_date__date=today)
    payments_count = payments_today.count()
    payments_sum = sum(float(p.amount) for p in payments_today)
    
    new_clients = Client.objects.filter(created_at__date=today).count()
    
    return f"""📊 <b>Отчёт за сегодня</b> ({today.strftime('%d.%m.%Y')})

📦 <b>Заказы:</b> {orders_count} шт на {int(orders_sum):,} сом
💰 <b>Оплаты:</b> {payments_count} шт на {int(payments_sum):,} сом
👥 <b>Новые клиенты:</b> {new_clients} чел

<i>CRM Аренда</i>""".replace(',', ' ')


def admin_report_week():
    """Отчёт за неделю"""
    from apps.clients.models import Client
    from apps.rental.models import RentalOrder, Payment
    
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    
    orders_week = RentalOrder.objects.filter(created_at__gte=week_ago)
    orders_count = orders_week.count()
    orders_sum = sum(float(o.get_current_total()) for o in orders_week)
    
    payments_week = Payment.objects.filter(payment_date__gte=week_ago)
    payments_sum = sum(float(p.amount) for p in payments_week)
    
    new_clients = Client.objects.filter(created_at__gte=week_ago).count()
    
    return f"""📈 <b>Отчёт за неделю</b>

📦 <b>Заказов:</b> {orders_count} на {int(orders_sum):,} сом
💰 <b>Оплат:</b> {int(payments_sum):,} сом
👥 <b>Новых клиентов:</b> {new_clients}

<i>{week_ago.strftime('%d.%m')} - {now.strftime('%d.%m.%Y')}</i>""".replace(',', ' ')


def admin_overdue_orders():
    """Просроченные заказы"""
    from apps.rental.models import RentalOrder
    
    now = timezone.now()
    overdue = []
    
    for order in RentalOrder.objects.filter(status='open').prefetch_related('items__product', 'client__phones'):
        overdue_items = [
            item for item in order.items.all()
            if item.quantity_remaining > 0 and item.planned_return_date < now
        ]
        if overdue_items:
            days = (now - min(i.planned_return_date for i in overdue_items)).days
            overdue.append((order, days))
    
    if not overdue:
        return "✅ <b>Просроченных заказов нет!</b>"
    
    overdue.sort(key=lambda x: x[1], reverse=True)
    
    text = f"⚠️ <b>Просроченные заказы ({len(overdue)}):</b>\n\n"
    
    for order, days in overdue[:10]:
        phones = ', '.join([p.phone_number for p in order.client.phones.all()])
        text += f"📦 <b>Заказ #{order.id}</b> — {days} дн.\n"
        text += f"👤 {order.client.get_full_name()}\n"
        text += f"📞 {phones}\n"
        text += f"💰 {int(order.get_current_total()):,} сом\n\n".replace(',', ' ')
    
    return text


def admin_debtors():
    """Должники"""
    from apps.clients.models import Client
    
    debtors = []
    for client in Client.objects.prefetch_related('phones'):
        balance = float(client.get_wallet_balance())
        if balance < 0:
            debtors.append((client, abs(balance)))
    
    if not debtors:
        return "✅ <b>Должников нет!</b>"
    
    debtors.sort(key=lambda x: x[1], reverse=True)
    
    text = f"💰 <b>Должники ({len(debtors)}):</b>\n\n"
    
    for client, debt in debtors[:10]:
        phones = ', '.join([p.phone_number for p in client.phones.all()])
        text += f"👤 <b>{client.get_full_name()}</b>\n"
        text += f"📞 {phones}\n"
        text += f"💸 Долг: <b>{int(debt):,} сом</b>\n\n".replace(',', ' ')
    
    return text


def admin_active_orders():
    """Активные заказы"""
    from apps.rental.models import RentalOrder
    
    orders = RentalOrder.objects.filter(status='open').select_related('client').prefetch_related('client__phones')[:15]
    
    if not orders:
        return "📭 <b>Нет активных заказов</b>"
    
    text = f"📦 <b>Активные заказы ({orders.count()}):</b>\n\n"
    
    for order in orders:
        phones = ', '.join([p.phone_number for p in order.client.phones.all()])
        text += f"📦 <b>#{order.id}</b> — {order.client.get_full_name()}\n"
        text += f"📞 {phones}\n"
        text += f"💰 {int(order.get_current_total()):,} сом\n".replace(',', ' ')
        text += f"📅 {order.created_at.strftime('%d.%m.%Y')}\n\n"
    
    return text


def admin_new_clients():
    """Новые клиенты"""
    from apps.clients.models import Client
    
    week_ago = timezone.now() - timedelta(days=7)
    clients = Client.objects.filter(created_at__gte=week_ago).order_by('-created_at').prefetch_related('phones')[:10]
    
    if not clients:
        return "📭 <b>Новых клиентов нет</b>"
    
    text = f"👥 <b>Новые клиенты за неделю ({clients.count()}):</b>\n\n"
    
    for client in clients:
        phones = ', '.join([p.phone_number for p in client.phones.all()])
        text += f"👤 <b>{client.get_full_name()}</b>\n"
        text += f"📞 {phones}\n"
        text += f"📅 {client.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    
    return text


# ============================================================
# ОБРАБОТЧИК CALLBACK (НАЖАТИЕ КНОПОК)
# ============================================================

def handle_callback_query(callback_query):
    """Обработка нажатия кнопок"""
    callback_id = callback_query['id']
    chat_id = callback_query['message']['chat']['id']
    data = callback_query['data']
    
    # Подтверждаем нажатие
    answer_callback_query(callback_id)
    
    # Админские команды
    if is_admin(chat_id):
        if data == 'admin_report_today':
            text = admin_report_today()
            send_telegram_message(chat_id, text, reply_markup=get_admin_keyboard())
            return
        
        elif data == 'admin_report_week':
            text = admin_report_week()
            send_telegram_message(chat_id, text, reply_markup=get_admin_keyboard())
            return
        
        elif data == 'admin_overdue':
            text = admin_overdue_orders()
            send_telegram_message(chat_id, text, reply_markup=get_admin_keyboard())
            return
        
        elif data == 'admin_debtors':
            text = admin_debtors()
            send_telegram_message(chat_id, text, reply_markup=get_admin_keyboard())
            return
        
        elif data == 'admin_active':
            text = admin_active_orders()
            send_telegram_message(chat_id, text, reply_markup=get_admin_keyboard())
            return
        
        elif data == 'admin_new_clients':
            text = admin_new_clients()
            send_telegram_message(chat_id, text, reply_markup=get_admin_keyboard())
            return
        
        elif data == 'admin_menu':
            text = "🔧 <b>Панель администратора</b>\n\nВыберите действие:"
            send_telegram_message(chat_id, text, reply_markup=get_admin_keyboard())
            return
    
    # Клиентские команды
    if data == 'balance':
        handle_balance(chat_id)
    
    elif data == 'orders':
        handle_orders(chat_id)
    
    elif data == 'contact':
        handle_contact(chat_id)
    
    elif data == 'help':
        handle_help(chat_id)
    
    elif data == 'back_to_menu':
        # Админ или клиент?
        if is_admin(chat_id):
            text = "🔧 <b>Панель администратора</b>"
            send_telegram_message(chat_id, text, reply_markup=get_admin_keyboard())
        else:
            text = "📱 <b>Главное меню</b>\n\nВыберите действие:"
            send_telegram_message(chat_id, text, reply_markup=get_client_keyboard())


# ============================================================
# ОБРАБОТЧИК КОМАНД /start, /help и т.д.
# ============================================================

def handle_command(message):
    """Обработка текстовых команд"""
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    
    if text == '/start':
        if is_admin(chat_id):
            # Админское меню
            welcome = "🔧 <b>Добро пожаловать, Администратор!</b>\n\nПанель управления CRM системой."
            send_telegram_message(chat_id, welcome, reply_markup=get_admin_keyboard())
        else:
            # Клиентское меню
            welcome = "👋 <b>Добро пожаловать!</b>\n\nЯ бот CRM системы аренды инструментов.\n\nВыберите действие:"
            send_telegram_message(chat_id, welcome, reply_markup=get_client_keyboard())
    
    elif text == '/balance':
        handle_balance(chat_id)
    
    elif text == '/orders':
        handle_orders(chat_id)
    
    elif text == '/contact':
        handle_contact(chat_id)
    
    elif text == '/help':
        handle_help(chat_id)
    
    elif text == '/menu':
        if is_admin(chat_id):
            send_telegram_message(chat_id, "🔧 Панель администратора", reply_markup=get_admin_keyboard())
        else:
            send_telegram_message(chat_id, "📱 Главное меню", reply_markup=get_client_keyboard())

from django.utils import timezone

def notify_overdue(order):
    """
    Ручная отправка уведомления клиенту о просрочке
    """
    from apps.clients.models import Client
    
    client = order.client
    
    if not client.telegram_id:
        return False
    
    now = timezone.now()
    
    overdue_items = [
        item for item in order.items.all()
        if item.quantity_remaining > 0 and item.planned_return_date < now
    ]
    
    if not overdue_items:
        return False
    
    days_overdue = (now - min(i.planned_return_date for i in overdue_items)).days
    
    text = f"""⚠️ <b>Просрочка по заказу #{order.id}</b>

Уважаемый {client.get_full_name()},

По вашему заказу есть просроченные позиции.
Просрочка: <b>{days_overdue} дн.</b>

Пожалуйста, верните инструмент или свяжитесь с нами.

💰 Текущая сумма: <b>{int(order.get_current_total()):,} сом</b>
""".replace(',', ' ')
    
    return send_telegram_message(client.telegram_id, text)