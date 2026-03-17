"""Email notification utilities for the CRM rental system."""
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone


def _send(subject, body, recipient_email):
    """Send a plain-text email. Returns True on success, False on failure."""
    if not recipient_email:
        return False
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"[email_utils] send error: {e}")
        return False


def notify_overdue_email(order):
    """Send overdue notification to client email."""
    client = order.client
    if not client.email:
        return False

    items_text = ''
    for item in order.items.all():
        items_text += f'  • {item.product.name} — {item.quantity_remaining} шт.\n'

    subject = f'Напоминание о возврате аренды — заказ #{order.id}'
    body = (
        f'Здравствуйте, {client.get_full_name()}!\n\n'
        f'Напоминаем, что срок аренды по заказу #{order.id} истёк.\n\n'
        f'Товары к возврату:\n{items_text}\n'
        f'Пожалуйста, свяжитесь с нами для уточнения деталей.\n\n'
        f'С уважением,\nСлужба аренды'
    )
    return _send(subject, body, client.email)


def notify_order_created_email(order):
    """Send order confirmation email to client."""
    client = order.client
    if not client.email:
        return False

    items_text = ''
    for item in order.items.all():
        date_str = item.planned_return_date.strftime('%d.%m.%Y') if item.planned_return_date else '—'
        items_text += f'  • {item.product.name} — {item.quantity_taken} шт. (вернуть до {date_str})\n'

    subject = f'Подтверждение заказа #{order.id}'
    body = (
        f'Здравствуйте, {client.get_full_name()}!\n\n'
        f'Ваш заказ #{order.id} оформлен.\n\n'
        f'Товары:\n{items_text}\n'
        f'Если у вас есть вопросы, свяжитесь с нами.\n\n'
        f'С уважением,\nСлужба аренды'
    )
    return _send(subject, body, client.email)


def notify_order_closed_email(order):
    """Send order closure/return confirmation email to client."""
    client = order.client
    if not client.email:
        return False

    subject = f'Заказ #{order.id} закрыт — спасибо!'
    body = (
        f'Здравствуйте, {client.get_full_name()}!\n\n'
        f'Ваш заказ #{order.id} успешно закрыт. Спасибо за аренду!\n\n'
        f'Ждём вас снова.\n\n'
        f'С уважением,\nСлужба аренды'
    )
    return _send(subject, body, client.email)
