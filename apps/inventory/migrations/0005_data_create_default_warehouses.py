from django.db import migrations


def create_default_warehouses(apps, schema_editor):
    Warehouse = apps.get_model('inventory', 'Warehouse')
    User = apps.get_model('auth', 'User')
    Product = apps.get_model('inventory', 'Product')

    # Create default warehouse for each director (is_superuser=True, is_staff=False)
    # and for the creator (is_superuser=True, is_staff=True)
    for user in User.objects.filter(is_superuser=True, is_active=True):
        wh = Warehouse.objects.create(
            owner=user,
            name='Основной склад',
            description='Склад по умолчанию',
        )
        # Assign all existing products of this user to default warehouse
        Product.objects.filter(owner=user, warehouse__isnull=True).update(warehouse=wh)


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0004_warehouse_product_warehouse_fk'),
    ]

    operations = [
        migrations.RunPython(create_default_warehouses, migrations.RunPython.noop),
    ]
