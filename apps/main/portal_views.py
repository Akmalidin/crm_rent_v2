"""Client portal views — public pages accessed via unique token."""
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404
from django.contrib import messages
from django.utils import timezone
from apps.main.models import ClientPortalToken, BookingRequest
from apps.clients.models import Client, ClientPhone
from apps.inventory.models import Product


def _get_client(token):
    """Resolve token to client; raise 404 if invalid."""
    pt = get_object_or_404(ClientPortalToken, token=token, is_active=True)
    return pt.client


def portal_login(request):
    """Client login by phone number."""
    error = ''
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        # Normalize: keep only digits and leading +
        digits = ''.join(c for c in phone if c.isdigit())
        if not digits:
            error = 'Введите номер телефона'
        else:
            # Search by phone number (try with +)
            cp = ClientPhone.objects.filter(phone_number__endswith=digits[-9:]).select_related('client').first()
            if not cp:
                # Also try exact match
                cp = ClientPhone.objects.filter(phone_number='+' + digits).select_related('client').first()
            if cp:
                client = cp.client
                token_obj, _ = ClientPortalToken.objects.get_or_create(client=client)
                return redirect('main:portal_catalog', token=token_obj.token)
            else:
                error = 'Клиент с таким номером не найден'

    return render(request, 'portal/login.html', {'error': error})


def portal_catalog(request, token):
    """Product catalog — browse available tools."""
    client = _get_client(token)
    owner = client.owner
    products = Product.objects.filter(owner=owner, is_active=True).select_related('category')
    categories = {}
    for p in products:
        cat = p.category.name if p.category else 'Без категории'
        categories.setdefault(cat, []).append(p)

    return render(request, 'portal/catalog.html', {
        'portal_client': client,
        'categories': categories,
        'products': products,
    })


def portal_book(request, token, product_id):
    """Book a product — create a BookingRequest."""
    client = _get_client(token)
    product = get_object_or_404(Product, id=product_id, owner=client.owner, is_active=True)

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        start_date = request.POST.get('start_date', '')
        end_date = request.POST.get('end_date', '')
        comment = request.POST.get('comment', '').strip()

        if not start_date or not end_date:
            return render(request, 'portal/book.html', {
                'portal_client': client, 'product': product,
                'error': 'Укажите даты начала и окончания',
            })

        BookingRequest.objects.create(
            client=client,
            product=product,
            quantity=max(1, min(quantity, product.quantity_available)),
            start_date=start_date,
            end_date=end_date,
            comment=comment,
        )

        # Notify director via Telegram
        try:
            from apps.main.telegram_bot_complete import send_telegram_message
            owner = client.owner
            profile = owner.profile if hasattr(owner, 'profile') else None
            chat_id = getattr(profile, 'telegram_chat_id', '') if profile else ''
            if chat_id:
                text = (
                    f"📩 <b>Новая заявка на бронирование</b>\n\n"
                    f"👤 Клиент: {client.get_full_name()}\n"
                    f"🔧 Товар: {product.name}\n"
                    f"📦 Количество: {quantity}\n"
                    f"📅 {start_date} — {end_date}\n"
                )
                if comment:
                    text += f"💬 {comment}\n"
                send_telegram_message(chat_id, text)
        except Exception:
            pass

        # Push SSE уведомление директору
        try:
            from apps.main.notification_utils import push_to_owner
            push_to_owner(client.owner,
                          f'📩 Новая заявка от {client.get_full_name()}',
                          f'{product.name} × {quantity} шт.',
                          type='booking', link='/bookings/')
        except Exception:
            pass

        return redirect('main:portal_my_bookings', token=token)

    return render(request, 'portal/book.html', {
        'portal_client': client,
        'product': product,
    })


def portal_my_bookings(request, token):
    """Client's booking requests."""
    client = _get_client(token)
    bookings = BookingRequest.objects.filter(client=client).select_related('product')
    return render(request, 'portal/my_bookings.html', {
        'portal_client': client,
        'bookings': bookings,
    })


def portal_my_orders(request, token):
    """Client's actual rental orders."""
    client = _get_client(token)
    orders = client.rental_orders.prefetch_related('items__product').order_by('-created_at')
    return render(request, 'portal/my_orders.html', {
        'portal_client': client,
        'orders': orders,
    })
