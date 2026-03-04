from django.shortcuts import render, redirect, get_object_or_404
from .models import Client, ClientPhone
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def _log(user, action, desc):
    try:
        from apps.main.views import log_activity
        log_activity(user, action, desc)
    except Exception:
        pass


def _get_owner(user):
    """Возвращает владельца тенанта для данного пользователя."""
    if user.is_superuser:
        return user
    try:
        owner = user.profile.owner
        return owner if owner else user
    except Exception:
        return user


def create_client(request):
    '''Создать нового клиента'''
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        middle_name = request.POST.get('middle_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        passport_front = request.FILES.get('passport_front')
        passport_back = request.FILES.get('passport_back')

        if not passport_front or not passport_back:
            messages.error(request, 'Необходимо загрузить фото обеих сторон паспорта')
            return render(request, 'clients/create.html', {})

        owner = _get_owner(request.user)

        # Создаём клиента
        client = Client.objects.create(
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            passport_front=passport_front,
            passport_back=passport_back,
            owner=owner,
        )

        # Добавляем телефон
        if phone:
            ClientPhone.objects.create(
                client=client,
                phone_number=phone,
                is_primary=True
            )

        messages.success(request, f'Клиент {client.get_full_name()} создан!')
        _log(request.user, 'create_client', f'Создал клиента {client.get_full_name()}')
        return redirect('main:client_detail', client_id=client.id)

    return render(request, 'clients/create.html')


@login_required
def edit_client(request, client_id):
    '''Редактировать клиента'''
    client = get_object_or_404(Client, id=client_id)
    primary_phone = client.phones.filter(is_primary=True).first()

    if request.method == 'POST':
        client.first_name = request.POST.get('first_name', client.first_name).strip()
        client.last_name = request.POST.get('last_name', client.last_name).strip()
        client.middle_name = request.POST.get('middle_name', client.middle_name).strip()

        # Обновляем фото паспорта только если загружены новые
        if request.FILES.get('passport_front'):
            client.passport_front = request.FILES['passport_front']
        if request.FILES.get('passport_back'):
            client.passport_back = request.FILES['passport_back']

        client.telegram_id = request.POST.get('telegram_id', client.telegram_id or '').strip() or None
        client.save()

        # Обновляем основной телефон
        new_phone = request.POST.get('phone', '').strip()
        if new_phone:
            if primary_phone:
                primary_phone.phone_number = new_phone
                primary_phone.save()
            else:
                ClientPhone.objects.create(client=client, phone_number=new_phone, is_primary=True)

        messages.success(request, f'Данные клиента {client.get_full_name()} обновлены!')
        _log(request.user, 'edit_client', f'Изменил данные клиента {client.get_full_name()}')
        return redirect('main:client_detail', client_id=client.id)

    return render(request, 'clients/edit.html', {
        'client': client,
        'primary_phone': primary_phone,
    })