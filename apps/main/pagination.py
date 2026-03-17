"""Pagination helper for views."""
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

PER_PAGE = 25


def paginate(request, queryset, per_page=PER_PAGE):
    """
    Paginate a queryset and build a query string without 'page' param.
    Returns (page_obj, page_query_string).
    """
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Build query string without 'page' for template links
    params = request.GET.copy()
    params.pop('page', None)
    page_query = params.urlencode()

    return page_obj, page_query
