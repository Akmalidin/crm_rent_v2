from django import template
import builtins

register = template.Library()


@register.filter
def abs(value):
    try:
        return builtins.abs(value)
    except Exception:
        return value
