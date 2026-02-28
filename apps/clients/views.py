from django.shortcuts import render, redirect
from .models import Client, ClientPhone
from django.contrib import messages

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
            return render(request, 'clients/create.html')

        # Создаём клиента
        client = Client.objects.create(
            first_name=first_name,
            last_name=last_name,
            middle_name=middle_name,
            passport_front=passport_front,
            passport_back=passport_back,
        )

        # Добавляем телефон
        if phone:
            ClientPhone.objects.create(
                client=client,
                phone_number=phone,
                is_primary=True
            )

        messages.success(request, f'Клиент {client.get_full_name()} создан!')
        return redirect('main:client_detail', client_id=client.id)

    return render(request, 'clients/create.html')