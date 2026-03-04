def company_context(request):
    """Добавляет информацию о компании во все шаблоны"""
    from apps.company.models import CompanyProfile
    from django.contrib.auth import get_user_model

    company = CompanyProfile.get_company()

    # Количество пользователей, ожидающих одобрения (только для суперпользователей)
    pending_users_count = 0
    if request.user.is_authenticated and request.user.is_superuser:
        User = get_user_model()
        pending_users_count = User.objects.filter(is_active=False).count()

    # Непрочитанные сообщения от директоров (только для создателя системы)
    unread_messages_count = 0
    if request.user.is_authenticated and request.user.is_staff:
        from apps.main.models import DirectorMessage
        unread_messages_count = DirectorMessage.objects.filter(is_read=False).count()

    return {
        'company': company,
        'pending_users_count': pending_users_count,
        'unread_messages_count': unread_messages_count,
    }
