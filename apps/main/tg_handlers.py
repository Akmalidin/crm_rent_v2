"""
Callback and command handlers for the Telegram bot.
Separated to avoid heredoc/shell quoting issues during development.
"""
from .telegram_bot_complete import (
    send_telegram_message, answer_callback_query,
    is_creator, get_director_profile,
    get_admin_keyboard, get_admin_reply_keyboard,
    get_director_keyboard, get_director_reply_keyboard,
    get_client_reply_keyboard, get_client_keyboard,
    get_broadcast_menu_keyboard, get_dir_broadcast_menu_keyboard,
    get_broadcast_target_keyboard,
    admin_report_today, admin_report_week, admin_overdue_orders,
    admin_debtors, admin_active_orders, admin_new_clients,
    director_report_today, director_report_week,
    director_overdue_orders, director_debtors,
    director_active_orders, director_new_clients,
    handle_broadcast_overdue, handle_broadcast_debt,
    handle_dir_broadcast_overdue, handle_dir_broadcast_debt,
    handle_broadcast_directors, handle_dir_broadcast_employees,
    handle_balance, handle_orders, handle_contact, handle_help,
    _admin_states, _handle_custom_broadcast_send,
)


def handle_callback_query(callback_query):
    callback_id = callback_query['id']
    chat_id = callback_query['message']['chat']['id']
    data = callback_query['data']

    answer_callback_query(callback_id)

    # Одобрение/отклонение директоров (только создатель)
    if data.startswith('approve_') or data.startswith('reject_'):
        if not is_creator(chat_id):
            return
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if data.startswith('approve_'):
                user_id = int(data.split('_')[1])
                target_user = User.objects.get(id=user_id)
                target_user.is_active = True
                target_user.is_superuser = True
                target_user.is_staff = False
                target_user.save()
                from django.contrib.auth.models import Group
                from apps.main.models import UserProfile
                from apps.inventory.models import Warehouse
                admin_group, _ = Group.objects.get_or_create(name='Администратор')
                target_user.groups.add(admin_group)
                profile, _ = UserProfile.objects.get_or_create(user=target_user, defaults={'owner': None})
                profile.role = 'director'
                profile.needs_company_setup = True
                profile.save()
                Warehouse.objects.get_or_create(
                    owner=target_user, name='Основной склад',
                    defaults={'description': 'Склад по умолчанию'},
                )
                send_telegram_message(chat_id, f"Директор {target_user.username} одобрен!")
            elif data.startswith('reject_'):
                user_id = int(data.split('_')[1])
                target_user = User.objects.get(id=user_id)
                username = target_user.username
                target_user.delete()
                send_telegram_message(chat_id, f"Пользователь {username} отклонён и удалён.")
        except Exception as e:
            send_telegram_message(chat_id, f"Ошибка: {e}")
        return

    # Создатель
    if is_creator(chat_id):
        if data == 'admin_report_today':
            send_telegram_message(chat_id, admin_report_today(), reply_markup=get_admin_keyboard())
        elif data == 'admin_report_week':
            send_telegram_message(chat_id, admin_report_week(), reply_markup=get_admin_keyboard())
        elif data == 'admin_overdue':
            send_telegram_message(chat_id, admin_overdue_orders(), reply_markup=get_admin_keyboard())
        elif data == 'admin_debtors':
            send_telegram_message(chat_id, admin_debtors(), reply_markup=get_admin_keyboard())
        elif data == 'admin_active':
            send_telegram_message(chat_id, admin_active_orders(), reply_markup=get_admin_keyboard())
        elif data == 'admin_new_clients':
            send_telegram_message(chat_id, admin_new_clients(), reply_markup=get_admin_keyboard())
        elif data == 'broadcast_overdue':
            send_telegram_message(chat_id, "Рассылка о просрочке запущена...")
            handle_broadcast_overdue(chat_id)
        elif data == 'broadcast_debt':
            send_telegram_message(chat_id, "Рассылка о долге запущена...")
            handle_broadcast_debt(chat_id)
        elif data == 'broadcast_custom_start':
            _admin_states[str(chat_id)] = {'state': 'waiting_broadcast_text', 'role': 'creator'}
            send_telegram_message(chat_id, "Напишите текст сообщения для рассылки клиентам:")
        elif data in ('send_custom_all', 'send_custom_overdue', 'send_custom_debtors'):
            _handle_custom_broadcast_send(chat_id, data, role='creator')
        elif data == 'broadcast_directors_start':
            _admin_states[str(chat_id)] = {'state': 'waiting_directors_text', 'role': 'creator'}
            send_telegram_message(chat_id, "Напишите текст сообщения для рассылки директорам:")
        elif data == 'admin_menu':
            send_telegram_message(chat_id, "<b>Панель администратора</b>", reply_markup=get_admin_keyboard())
        elif data == 'back_to_menu':
            send_telegram_message(chat_id, "<b>Панель администратора</b>", reply_markup=get_admin_reply_keyboard())
            send_telegram_message(chat_id, "Выберите раздел:", reply_markup=get_admin_keyboard())
        return

    # Директор
    director_profile = get_director_profile(chat_id)
    if director_profile:
        if data == 'dir_report_today':
            send_telegram_message(chat_id, director_report_today(director_profile), reply_markup=get_director_keyboard())
        elif data == 'dir_report_week':
            send_telegram_message(chat_id, director_report_week(director_profile), reply_markup=get_director_keyboard())
        elif data == 'dir_overdue':
            send_telegram_message(chat_id, director_overdue_orders(director_profile), reply_markup=get_director_keyboard())
        elif data == 'dir_debtors':
            send_telegram_message(chat_id, director_debtors(director_profile), reply_markup=get_director_keyboard())
        elif data == 'dir_active':
            send_telegram_message(chat_id, director_active_orders(director_profile), reply_markup=get_director_keyboard())
        elif data == 'dir_new_clients':
            send_telegram_message(chat_id, director_new_clients(director_profile), reply_markup=get_director_keyboard())
        elif data == 'dir_broadcast_menu':
            send_telegram_message(chat_id, "<b>Рассылка клиентам</b>", reply_markup=get_dir_broadcast_menu_keyboard())
        elif data == 'dir_broadcast_overdue':
            send_telegram_message(chat_id, "Запускаю рассылку о просрочке...")
            handle_dir_broadcast_overdue(chat_id, director_profile)
        elif data == 'dir_broadcast_debt':
            send_telegram_message(chat_id, "Запускаю рассылку о долге...")
            handle_dir_broadcast_debt(chat_id, director_profile)
        elif data == 'dir_broadcast_custom_start':
            _admin_states[str(chat_id)] = {'state': 'waiting_broadcast_text', 'role': 'director'}
            send_telegram_message(chat_id, "Напишите текст сообщения для рассылки вашим клиентам:")
        elif data in ('dir_send_custom_all', 'dir_send_custom_overdue', 'dir_send_custom_debtors'):
            _handle_custom_broadcast_send(chat_id, data, role='director', director_profile=director_profile)
        elif data == 'dir_broadcast_employees_start':
            _admin_states[str(chat_id)] = {'state': 'waiting_employees_text', 'role': 'director'}
            send_telegram_message(chat_id, "Напишите текст сообщения для рассылки вашим сотрудникам:")
        elif data == 'dir_menu':
            send_telegram_message(chat_id, "<b>Панель директора</b>", reply_markup=get_director_keyboard())
        elif data == 'back_to_menu':
            send_telegram_message(chat_id, "<b>Панель директора</b>", reply_markup=get_director_reply_keyboard())
            send_telegram_message(chat_id, "Выберите раздел:", reply_markup=get_director_keyboard())
        return

    # Клиент
    if data == 'balance':
        handle_balance(chat_id)
    elif data == 'orders':
        handle_orders(chat_id)
    elif data == 'contact':
        handle_contact(chat_id)
    elif data == 'help':
        handle_help(chat_id)
    elif data == 'back_to_menu':
        send_telegram_message(chat_id, "Главное меню", reply_markup=get_client_reply_keyboard())


def handle_command(message):
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    first_name = message.get('from', {}).get('first_name', '')

    # Состояние ожидания текста рассылки
    state = _admin_states.get(str(chat_id), {})

    # Рассылка директорам (создатель)
    if state.get('state') == 'waiting_directors_text':
        _admin_states.pop(str(chat_id), None)
        send_telegram_message(chat_id, "Отправляю директорам...")
        handle_broadcast_directors(chat_id, text)
        return

    # Рассылка сотрудникам (директор)
    if state.get('state') == 'waiting_employees_text':
        _admin_states.pop(str(chat_id), None)
        dp = get_director_profile(chat_id)
        if dp:
            send_telegram_message(chat_id, "Отправляю сотрудникам...")
            handle_dir_broadcast_employees(chat_id, dp, text)
        return

    if state.get('state') == 'waiting_broadcast_text':
        role = state.get('role', 'creator')
        _admin_states[str(chat_id)] = {'state': 'waiting_broadcast_target', 'text': text, 'role': role}
        preview = text[:300] + ('...' if len(text) > 300 else '')
        prefix = 'dir_' if role == 'director' else ''
        send_telegram_message(
            chat_id,
            f"Текст принят. Кому отправить?\n\n<i>{preview}</i>",
            reply_markup=get_broadcast_target_keyboard(prefix=prefix)
        )
        return

    if text == '/myid':
        send_telegram_message(chat_id,
            f"Ваш Telegram ID:\n\n<code>{chat_id}</code>\n\n"
            "Скопируйте этот ID и вставьте в CRM -> Telegram профиль")
        return

    if text == '/start':
        if is_creator(chat_id):
            send_telegram_message(chat_id, "<b>Добро пожаловать, Администратор!</b>", reply_markup=get_admin_reply_keyboard())
            send_telegram_message(chat_id, "Выберите раздел:", reply_markup=get_admin_keyboard())
        else:
            director_profile = get_director_profile(chat_id)
            if director_profile:
                name = first_name or director_profile.user.get_full_name() or director_profile.user.username
                send_telegram_message(
                    chat_id,
                    f"<b>Добро пожаловать, {name}!</b>\n\nПанель директора CRM.",
                    reply_markup=get_director_reply_keyboard()
                )
                send_telegram_message(chat_id, "Выберите раздел:", reply_markup=get_director_keyboard())
            else:
                send_telegram_message(
                    chat_id,
                    f"<b>Добро пожаловать!</b>\n\nВаш ID: <code>{chat_id}</code>\n\n"
                    "Если вы директор — введите этот ID в CRM -> Telegram профиль.",
                    reply_markup=get_client_reply_keyboard()
                )
        return

    if text == '/balance':
        handle_balance(chat_id)
    elif text == '/orders':
        handle_orders(chat_id)
    elif text == '/contact':
        handle_contact(chat_id)
    elif text == '/help':
        handle_help(chat_id)
    elif text == '/menu':
        if is_creator(chat_id):
            send_telegram_message(chat_id, "Панель администратора", reply_markup=get_admin_reply_keyboard())
            send_telegram_message(chat_id, "Выберите раздел:", reply_markup=get_admin_keyboard())
        else:
            dp = get_director_profile(chat_id)
            if dp:
                send_telegram_message(chat_id, "Панель директора", reply_markup=get_director_reply_keyboard())
                send_telegram_message(chat_id, "Выберите раздел:", reply_markup=get_director_keyboard())
            else:
                send_telegram_message(chat_id, "Главное меню", reply_markup=get_client_reply_keyboard())

    # Reply keyboard — клиент
    elif text in ('\U0001f4b0 Мой баланс', 'Мой баланс'):
        handle_balance(chat_id)
    elif text in ('\U0001f4e6 Мои заказы', 'Мои заказы'):
        handle_orders(chat_id)
    elif text in ('\U0001f4de Контакты', 'Контакты'):
        handle_contact(chat_id)
    elif text in ('\u2753 Помощь', 'Помощь'):
        handle_help(chat_id)

    # Reply keyboard — создатель
    elif is_creator(chat_id):
        tl = text.lower()
        if 'сегодня' in tl:
            send_telegram_message(chat_id, admin_report_today(), reply_markup=get_admin_keyboard())
        elif 'неделю' in tl:
            send_telegram_message(chat_id, admin_report_week(), reply_markup=get_admin_keyboard())
        elif 'просроч' in tl:
            send_telegram_message(chat_id, admin_overdue_orders(), reply_markup=get_admin_keyboard())
        elif 'должник' in tl:
            send_telegram_message(chat_id, admin_debtors(), reply_markup=get_admin_keyboard())
        elif 'активн' in tl:
            send_telegram_message(chat_id, admin_active_orders(), reply_markup=get_admin_keyboard())
        elif 'клиент' in tl:
            send_telegram_message(chat_id, admin_new_clients(), reply_markup=get_admin_keyboard())
        elif 'рассылк' in tl:
            _admin_states.pop(str(chat_id), None)
            send_telegram_message(chat_id, "<b>Массовая рассылка</b>", reply_markup=get_broadcast_menu_keyboard())

    # Reply keyboard — директор
    else:
        dp = get_director_profile(chat_id)
        if dp:
            tl = text.lower()
            if 'отчёт' in tl or 'отчет' in tl:
                send_telegram_message(chat_id, director_report_today(dp), reply_markup=get_director_keyboard())
            elif 'просроч' in tl:
                send_telegram_message(chat_id, director_overdue_orders(dp), reply_markup=get_director_keyboard())
            elif 'должник' in tl:
                send_telegram_message(chat_id, director_debtors(dp), reply_markup=get_director_keyboard())
            elif 'активн' in tl:
                send_telegram_message(chat_id, director_active_orders(dp), reply_markup=get_director_keyboard())
            elif 'рассылк' in tl:
                _admin_states.pop(str(chat_id), None)
                send_telegram_message(chat_id, "<b>Рассылка клиентам</b>", reply_markup=get_dir_broadcast_menu_keyboard())
