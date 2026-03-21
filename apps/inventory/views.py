from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Category, Product, Warehouse
from apps.main.pagination import paginate


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


@login_required
def products_list(request):
    from django.http import HttpResponseRedirect
    owner = _get_owner(request.user)
    categories = Category.objects.filter(owner=owner).order_by('name')
    cat_filter = request.GET.get('category', '')

    # Toggle rain_applicable on a category (POST)
    if request.method == 'POST' and 'toggle_rain' in request.POST:
        cat_id = request.POST.get('toggle_rain')
        try:
            cat = Category.objects.get(id=cat_id, owner=owner)
            cat.rain_applicable = not cat.rain_applicable
            cat.save(update_fields=['rain_applicable'])
        except Category.DoesNotExist:
            pass
        return HttpResponseRedirect(request.path + (f'?category={cat_id}' if cat_id else ''))

    selected_cat = None
    page_obj = None
    page_query = ''
    total_rented = 0
    search_query = request.GET.get('search', '').strip()

    if cat_filter:
        products_qs = Product.objects.filter(owner=owner, category_id=cat_filter).select_related('category').order_by('name')
        total_rented = sum(p.quantity_rented for p in products_qs)
        page_obj, page_query = paginate(request, products_qs)
        selected_cat = categories.filter(id=cat_filter).first()
    elif search_query:
        # Cross-category product search
        products_qs = Product.objects.filter(
            owner=owner, name__icontains=search_query
        ).select_related('category').order_by('category__name', 'name')
        page_obj, page_query = paginate(request, products_qs)
        total_rented = sum(p.quantity_rented for p in products_qs)
    else:
        # Category overview: annotate stats on each category
        for cat in categories:
            cat_products = cat.products.filter(owner=owner)
            cat.total_count = cat_products.count()
            cat.available_count = sum(p.quantity_available for p in cat_products)
            cat.rented_count = sum(p.quantity_rented for p in cat_products)

    return render(request, 'inventory/products_list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'page_query': page_query,
        'categories': categories,
        'cat_filter': cat_filter,
        'total_rented': total_rented,
        'selected_cat': selected_cat,
        'search_query': search_query,
    })


@login_required
def create_product(request):
    owner = _get_owner(request.user)
    categories = Category.objects.filter(owner=owner).order_by('name')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        cat_id = request.POST.get('category', '').strip()
        new_cat = request.POST.get('new_category', '').strip()
        qty = request.POST.get('quantity_total', '0').strip()
        price_day = request.POST.get('price_per_day', '0').strip()
        price_hour = request.POST.get('price_per_hour', '0').strip()

        if not name:
            messages.error(request, 'Введите название товара')
            return render(request, 'inventory/create_product.html', {'categories': categories})

        # Create new category on the fly if provided
        if new_cat:
            category, _ = Category.objects.get_or_create(name=new_cat, defaults={'owner': owner})
        elif cat_id:
            category = get_object_or_404(Category, id=cat_id, owner=owner)
        else:
            messages.error(request, 'Выберите или введите категорию')
            return render(request, 'inventory/create_product.html', {'categories': categories})

        product = Product.objects.create(
            name=name,
            category=category,
            quantity_total=int(qty) if qty.isdigit() else 0,
            price_per_day=price_day or 0,
            price_per_hour=price_hour or 0,
            owner=owner,
        )
        photo = request.FILES.get('photo')
        if photo:
            product.photo = photo
            product.save(update_fields=['photo'])
        messages.success(request, f'Товар «{product.name}» добавлен!')
        _log(request.user, 'create_product', f'Создал товар «{product.name}»')
        return redirect('main:products_list')

    return render(request, 'inventory/create_product.html', {'categories': categories})


@login_required
def edit_product(request, product_id):
    owner = _get_owner(request.user)
    product = get_object_or_404(Product, id=product_id, owner=owner)
    categories = Category.objects.filter(owner=owner).order_by('name')
    if request.method == 'POST':
        product.name = request.POST.get('name', product.name).strip()
        cat_id = request.POST.get('category', '').strip()
        new_cat = request.POST.get('new_category', '').strip()
        qty = request.POST.get('quantity_total', str(product.quantity_total)).strip()
        price_day = request.POST.get('price_per_day', str(product.price_per_day)).strip()
        price_hour = request.POST.get('price_per_hour', str(product.price_per_hour)).strip()
        product.is_active = request.POST.get('is_active') == 'on'

        if new_cat:
            product.category, _ = Category.objects.get_or_create(name=new_cat, defaults={'owner': owner})
        elif cat_id:
            product.category = get_object_or_404(Category, id=cat_id, owner=owner)

        product.quantity_total = int(qty) if qty.isdigit() else product.quantity_total
        product.price_per_day = price_day or product.price_per_day
        product.price_per_hour = price_hour or product.price_per_hour
        photo = request.FILES.get('photo')
        if photo:
            product.photo = photo
        elif request.POST.get('remove_photo'):
            product.photo = None
        product.save()
        messages.success(request, f'Товар «{product.name}» обновлён!')
        _log(request.user, 'edit_product', f'Изменил товар «{product.name}»')
        return redirect('main:products_list')

    return render(request, 'inventory/edit_product.html', {
        'product': product,
        'categories': categories,
    })


@login_required
def product_report(request, product_id):
    """Отчёт по товару — кто и когда брал"""
    from apps.rental.models import OrderItem, RentalOrder
    from django.utils import timezone

    owner = _get_owner(request.user)
    product = get_object_or_404(Product, id=product_id, owner=owner)

    items = (OrderItem.objects
             .filter(product=product, order__client__owner=owner)
             .select_related('order', 'order__client')
             .prefetch_related('order__client__phones')
             .order_by('-order__created_at'))

    # Stats
    total_rentals = items.count()
    active_rentals = items.filter(order__status=RentalOrder.STATUS_OPEN, quantity_remaining__gt=0).count()
    total_quantity_rented = sum(i.quantity_taken for i in items)

    now = timezone.now()

    context = {
        'product': product,
        'items': items,
        'total_rentals': total_rentals,
        'active_rentals': active_rentals,
        'total_quantity_rented': total_quantity_rented,
        'now': now,
    }
    return render(request, 'inventory/product_report.html', context)


@login_required
def warehouse_list(request):
    """Список складов"""
    owner = _get_owner(request.user)
    warehouses = Warehouse.objects.filter(owner=owner)

    try:
        max_wh = request.user.profile.max_warehouses
    except Exception:
        max_wh = 1
    can_create = warehouses.count() < max_wh

    context = {
        'warehouses': warehouses,
        'can_create': can_create,
        'max_warehouses': max_wh,
    }
    return render(request, 'inventory/warehouse_list.html', context)


@login_required
def create_warehouse(request):
    """Создать склад"""
    owner = _get_owner(request.user)
    try:
        max_wh = request.user.profile.max_warehouses
    except Exception:
        max_wh = 1

    current_count = Warehouse.objects.filter(owner=owner).count()
    if current_count >= max_wh:
        messages.error(request, f'Достигнут лимит складов ({max_wh}). Обратитесь к создателю системы для увеличения лимита.')
        return redirect('main:warehouse_list')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if not name:
            messages.error(request, 'Укажите название склада')
            return render(request, 'inventory/create_warehouse.html', {})
        Warehouse.objects.create(owner=owner, name=name, description=description)
        messages.success(request, f'Склад "{name}" создан!')
        return redirect('main:warehouse_list')

    return render(request, 'inventory/create_warehouse.html', {})


@login_required
def delete_warehouse(request, warehouse_id):
    """Удалить склад (только если пустой)"""
    owner = _get_owner(request.user)
    wh = get_object_or_404(Warehouse, id=warehouse_id, owner=owner)
    if wh.products.exists():
        messages.error(request, 'Нельзя удалить склад с товарами. Сначала переместите товары.')
        return redirect('main:warehouse_list')
    if Warehouse.objects.filter(owner=owner).count() <= 1:
        messages.error(request, 'Нельзя удалить единственный склад.')
        return redirect('main:warehouse_list')
    wh.delete()
    messages.success(request, 'Склад удалён.')
    return redirect('main:warehouse_list')
