"""Cache invalidation helpers."""
from django.core.cache import cache


def invalidate_dashboard(owner_id):
    """Clear dashboard cache for a specific owner."""
    cache.delete(f'dashboard_{owner_id}')
