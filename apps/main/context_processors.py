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

    # Непрочитанные обращения (для создателя) и непрочитанные ответы (для директора)
    unread_messages_count = 0
    unread_reply_count = 0
    if request.user.is_authenticated:
        from apps.main.models import TicketReply
        if request.user.is_staff:
            # Непрочитанные сообщения от директоров
            unread_messages_count = TicketReply.objects.filter(
                is_read=False
            ).exclude(author__is_staff=True).values('ticket').distinct().count()
        else:
            # Непрочитанные ответы от создателя для этого пользователя
            unread_reply_count = TicketReply.objects.filter(
                ticket__sender=request.user,
                is_read=False,
                author__is_staff=True,
            ).values('ticket').distinct().count()

    return {
        'company': company,
        'pending_users_count': pending_users_count,
        'unread_messages_count': unread_messages_count,
        'unread_reply_count': unread_reply_count,
    }
