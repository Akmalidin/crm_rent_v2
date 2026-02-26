# apps/rental/utils.py (новый файл)
from decimal import Decimal

def calculate_order_debt(order, total_paid_for_order, client_balance):
    """
    Рассчитать долг по заказу с учётом общего баланса клиента
    
    Если у клиента есть аванс (положительный баланс), он покрывает долг по заказам
    """
    current_cost = Decimal(str(order.get_current_total()))
    paid = Decimal(str(total_paid_for_order))
    
    # Базовый долг по заказу
    base_debt = current_cost - paid
    
    # Если есть аванс клиента, он уменьшает долг
    if client_balance > 0:
        # Аванс покрывает часть или весь долг
        if Decimal(str(client_balance)) >= base_debt:
            return Decimal('0')  # Аванс покрыл весь долг
        else:
            return base_debt - Decimal(str(client_balance))
    
    return base_debt


def get_order_groups_for_client(client, now):
    """
    Получить сгруппированные заказы с событиями для клиента
    Используется в client_detail и history
    """
    import re
    from apps.rental.models import ReturnDocument
    from django.utils import timezone
    from decimal import Decimal
    
    order_groups = []
    client_balance = client.get_wallet_balance()
    
    for order in client.rental_orders.all().order_by('-created_at'):
        order_events = []
        
        # 1. Создание заказа
        order_events.append({
            'type': 'order_created',
            'date': order.created_at,
            'description': 'Создан заказ',
            'items': list(order.items.all()),
            'total': float(order.get_original_total()),
        })
        
        # 2. Возвраты
        for order_item in order.items.all():
            for return_item in order_item.returns.all():
                order_events.append({
                    'type': 'return',
                    'date': return_item.return_document.return_date,
                    'description': 'Возврат товаров',
                    'return_item': return_item,
                })
        
        # 3. Оплаты
        for payment in client.payments.all():
            if payment.notes and f'#{order.id}' in payment.notes:
                payment_for_order = None
                if 'Распределение:' in payment.notes:
                    for line in payment.notes.split('\n'):
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
        
        # 4. Просрочки
        if order.status == 'open':
            for item in order.items.all():
                if item.quantity_remaining > 0 and item.planned_return_date < now:
                    overdue_time = now - item.planned_return_date
                    overdue_days = overdue_time.days
                    overdue_hours = overdue_time.seconds // 3600
                    
                    if overdue_time.total_seconds() < 86400:
                        hourly_rate = Decimal(str(item.price_per_day)) / 24
                        overdue_cost = Decimal(str(overdue_hours)) * hourly_rate * item.quantity_remaining
                    else:
                        overdue_cost = Decimal(str(overdue_days)) * Decimal(str(item.price_per_day)) * item.quantity_remaining
                    
                    order_events.append({
                        'type': 'overdue_charge',
                        'date': now,
                        'description': f'Начисление за просрочку: {item.product.name}',
                        'product_name': item.product.name,
                        'quantity': item.quantity_remaining,
                        'overdue_days': overdue_days,
                        'overdue_hours': overdue_hours,
                        'overdue_cost': float(overdue_cost),
                        'planned_return_date': item.planned_return_date,
                    })
        
        # Сортируем события
        order_events.sort(key=lambda x: x['date'])
        
        # Считаем итоги
        total_paid_for_order = sum(e.get('amount', 0) for e in order_events if e['type'] == 'payment')
        current_order_cost = float(order.get_current_total())
        
        # Используем общий баланс клиента для расчёта долга
        if client_balance > 0:
            # Если есть аванс, показываем долг с учётом покрытия
            order_debt = max(0, current_order_cost - total_paid_for_order - client_balance)
        else:
            order_debt = current_order_cost - total_paid_for_order
        
        has_unreturned = order.items.filter(quantity_remaining__gt=0).exists()
        is_overdue = order.items.filter(quantity_remaining__gt=0, planned_return_date__lt=now).exists()
        
        order_groups.append({
            'order': order,
            'events': order_events,
            'total_paid': total_paid_for_order,
            'current_cost': current_order_cost,
            'debt': order_debt,
            'has_unreturned_items': has_unreturned,
            'is_overdue': is_overdue,
        })
    
    return order_groups