from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.rental.models import OrderItem

@receiver(post_save, sender=OrderItem)
def update_product_availability_on_save(sender, instance, **kwargs):
    """При создании/изменении аренды обновляем доступность"""
    instance.product.update_available_quantity()

@receiver(post_delete, sender=OrderItem)
def update_product_availability_on_delete(sender, instance, **kwargs):
    """При удалении аренды обновляем доступность"""
    instance.product.update_available_quantity()