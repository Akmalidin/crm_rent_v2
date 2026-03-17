"""
Утилиты для создания уведомлений.

Использование:
    from apps.main.notification_utils import push_notification, push_to_owner

    push_notification(user_id, 'Новый заказ', '...', type='order', link='/orders/5/')
    push_to_owner(owner, 'Оплата принята', amount_str, type='payment', link='/payment/')
"""
from apps.main.models import Notification


def push_notification(user_id, title, message='', type='info', link=''):
    """Создаёт уведомление для пользователя по ID."""
    try:
        Notification.objects.create(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            link=link,
        )
    except Exception:
        pass


def push_to_owner(owner, title, message='', type='info', link=''):
    """Создаёт уведомление для владельца тенанта (директора)."""
    push_notification(owner.id, title, message, type, link)
