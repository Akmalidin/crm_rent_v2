"""
Автоматические напоминания — запускать через cron каждый час:
  python manage.py send_notifications

Cron (каждый час):
  0 * * * * /path/to/venv/bin/python /path/to/manage.py send_notifications

Типы напоминаний:
  1. За 1 день до возврата — предупреждение клиенту
  2. В день возврата — напоминание клиенту
  3. Просроченные — уведомление директору (раз в день, утром)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Отправить автоматические уведомления'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Не отправлять, только показать что было бы отправлено')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        now = timezone.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        from apps.rental.models import OrderItem
        from apps.main.telegram_bot_complete import send_telegram_message

        sent_overdue = 0
        sent_tomorrow = 0
        sent_today = 0

        # ── 1. Завтра срок возврата ────────────────────────────────────────────
        items_tomorrow = (
            OrderItem.objects
            .filter(order__status=RentalOrder.STATUS_OPEN, quantity_remaining__gt=0,
                    planned_return_date__date=tomorrow)
            .select_related('order__client', 'product')
        )
        for item in items_tomorrow:
            client = item.order.client
            tg_id = client.telegram_id
            if tg_id and not dry_run:
                try:
                    send_telegram_message(
                        tg_id,
                        f"⏰ <b>Напоминание о возврате</b>\n\n"
                        f"Завтра ({tomorrow.strftime('%d.%m.%Y')}) нужно вернуть:\n"
                        f"📦 {item.product.name} × {item.quantity_remaining} шт.\n\n"
                        f"Заказ #{item.order.id}"
                    )
                    sent_tomorrow += 1
                except Exception:
                    pass
            else:
                sent_tomorrow += 1
            self.stdout.write(f"  📅 Завтра: {client} — {item.product.name}")

        # ── 2. Сегодня срок возврата ───────────────────────────────────────────
        items_today = (
            OrderItem.objects
            .filter(order__status=RentalOrder.STATUS_OPEN, quantity_remaining__gt=0,
                    planned_return_date__date=today)
            .select_related('order__client', 'product')
        )
        for item in items_today:
            client = item.order.client
            tg_id = client.telegram_id
            if tg_id and not dry_run:
                try:
                    send_telegram_message(
                        tg_id,
                        f"⚠️ <b>Сегодня возврат!</b>\n\n"
                        f"Сегодня ({today.strftime('%d.%m.%Y')}) нужно вернуть:\n"
                        f"📦 {item.product.name} × {item.quantity_remaining} шт.\n\n"
                        f"Заказ #{item.order.id}"
                    )
                    sent_today += 1
                except Exception:
                    pass
            else:
                sent_today += 1
            self.stdout.write(f"  🔔 Сегодня: {client} — {item.product.name}")

        # ── 3. Просроченные — директору (только с 9:00 до 10:00) ──────────────
        local_hour = timezone.localtime(now).hour
        if local_hour == 9 or dry_run:
            overdue_items = (
                OrderItem.objects
                .filter(order__status=RentalOrder.STATUS_OPEN, quantity_remaining__gt=0,
                        planned_return_date__lt=now)
                .select_related('order__client__owner', 'product')
            )
            # Группируем по директорам
            by_director = {}
            for item in overdue_items:
                owner = item.order.client.owner
                if owner not in by_director:
                    by_director[owner] = []
                by_director[owner].append(item)

            from django.conf import settings as _settings
            from apps.main.models import UserProfile
            for director, items in by_director.items():
                try:
                    profile = director.profile
                    chat_id = profile.telegram_chat_id
                except Exception:
                    chat_id = None

                # Для создателя системы — берём TELEGRAM_ADMIN_CHAT_ID
                if director.is_staff:
                    chat_id = getattr(_settings, 'TELEGRAM_ADMIN_CHAT_ID', None)

                if not chat_id:
                    continue

                lines = [f"🔴 <b>Просроченные заказы — {today.strftime('%d.%m.%Y')}</b>\n"]
                for item in items[:10]:
                    days_over = (now - item.planned_return_date).days
                    lines.append(
                        f"• {item.order.client.get_full_name()} — {item.product.name} "
                        f"(+{days_over} дн.)"
                    )
                if len(items) > 10:
                    lines.append(f"...и ещё {len(items)-10} позиций")

                if not dry_run:
                    try:
                        send_telegram_message(chat_id, "\n".join(lines))
                        sent_overdue += len(items)
                    except Exception:
                        pass
                else:
                    sent_overdue += len(items)
                self.stdout.write(f"  🔴 Просрочка директору {director.username}: {len(items)} шт.")

        msg = f'Done! Tomorrow:{sent_tomorrow} Today:{sent_today} Overdue:{sent_overdue}'
        if dry_run:
            msg += ' (dry-run)'
        self.stdout.write(self.style.SUCCESS(msg))
