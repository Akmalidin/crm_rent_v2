from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Product, Category


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
    owner = _get_owner(request.user)
    products = Product.objects.filter(owner=owner).select_related('category').order_by('category__name', 'name')
    categories = Category.objects.filter(owner=owner).order_by('name')
    cat_filter = request.GET.get('category', '')
    if cat_filter:
        products = products.filter(category_id=cat_filter)
    total_rented = sum(p.quantity_rented for p in products)
    return render(request, 'inventory/products_list.html', {
        'products': products,
        'categories': categories,
        'cat_filter': cat_filter,
        'total_rented': total_rented,
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
        messages.success(request, f'Товар «{product.name}» добавлен!')
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
        product.save()
        messages.success(request, f'Товар «{product.name}» обновлён!')
        return redirect('main:products_list')

    return render(request, 'inventory/edit_product.html', {
        'product': product,
        'categories': categories,
    })
