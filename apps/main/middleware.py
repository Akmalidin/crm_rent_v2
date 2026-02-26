from django.shortcuts import redirect
from django.urls import reverse

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