def company_context(request):
    """Добавляет информацию о компании во все шаблоны"""
    from apps.company.models import CompanyProfile
    
    company = CompanyProfile.get_company()
    
    return {
        'company': company,
    }