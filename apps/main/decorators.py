
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def admin_required(view_func):
    """Требуется администратор"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser or request.user.groups.filter(name='Администратор').exists():
            return view_func(request, *args, **kwargs)
        
        messages.error(request, '🔒 Доступ запрещён! Требуются права администратора.')
        return redirect('main:dashboard')
    return wrapper


def manager_required(view_func):
    """Требуется менеджер или выше"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if (request.user.is_superuser or 
            request.user.groups.filter(name__in=['Администратор', 'Менеджер']).exists()):
            return view_func(request, *args, **kwargs)
        
        messages.error(request, '🔒 Доступ запрещён! Требуются права менеджера или администратора.')
        return redirect('main:dashboard')
    return wrapper


def cashier_required(view_func):
    """Требуется кассир или выше"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if (request.user.is_superuser or 
            request.user.groups.filter(name__in=['Администратор', 'Менеджер', 'Кассир']).exists()):
            return view_func(request, *args, **kwargs)
        
        messages.error(request, '🔒 Доступ запрещён! У вас недостаточно прав для этого действия.')
        return redirect('main:dashboard')
    return wrapper


def permission_required_with_message(perm, message=None):
    """Декоратор с кастомным сообщением"""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.has_perm(perm):
                return view_func(request, *args, **kwargs)
            
            msg = message or f'🔒 Доступ запрещён! Требуется разрешение: {perm}'
            messages.error(request, msg)
            return redirect('main:dashboard')
        return wrapper
    return decorator