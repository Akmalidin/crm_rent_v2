from django.shortcuts import redirect
from django.urls import reverse
import time


# Пути, которые НЕ логируем (статика, медиа, polling, beacon сам себя)
_SKIP_PREFIXES = ('/static/', '/media/', '/favicon', '/robots')
_SKIP_PATHS = {'/notifications/poll/', '/notifications/mark-read/'}


class AuditMiddleware:
    """Логирует каждый HTTP-запрос в RequestLog"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        t0 = time.monotonic()
        response = self.get_response(request)
        elapsed_ms = int((time.monotonic() - t0) * 1000)

        path = request.path
        if (any(path.startswith(p) for p in _SKIP_PREFIXES)
                or path in _SKIP_PATHS):
            return response

        try:
            from apps.main.models import RequestLog
            user = request.user if request.user.is_authenticated else None
            username = user.username if user else ''
            ip = (request.META.get('HTTP_X_FORWARDED_FOR', '') or
                  request.META.get('REMOTE_ADDR', ''))
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            RequestLog.objects.create(
                user=user,
                username=username,
                ip=ip or None,
                method=request.method,
                path=path,
                query=request.META.get('QUERY_STRING', '')[:500],
                status_code=response.status_code,
                response_ms=elapsed_ms,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                referer=request.META.get('HTTP_REFERER', '')[:500],
            )
        except Exception:
            pass

        return response

class CompanySetupMiddleware:
    """Middleware для проверки настройки компании"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Пропускаем для неавторизованных
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Пропускаем для служебных URL
        allowed_paths = [
            '/admin/',
            '/logout/',
            '/setup-company/',
            '/static/',
            '/media/',
        ]
        
        if any(request.path.startswith(path) for path in allowed_paths):
            return self.get_response(request)
        
        # Проверяем настройку компании
        from apps.company.models import CompanyProfile
        company = CompanyProfile.get_company()
        
        # Если компания не настроена - редирект на настройку
        if not company.company_name or company.company_name == 'Моя компания':
            if request.path != reverse('main:setup_company'):
                return redirect('main:setup_company')
        
        return self.get_response(request)
    
class TurboMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Если Turbo запрос и редирект, добавляем заголовок
        if request.headers.get('Turbo-Frame') and 300 <= response.status_code < 400:
            response['Turbo-Visit'] = response['Location']
        
        return response