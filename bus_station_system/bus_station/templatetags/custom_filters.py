# bus_station/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def sum_attr(queryset, attr_name):
    """Сума значень атрибута в queryset"""
    total = 0
    for item in queryset:
        value = getattr(item, attr_name, 0)
        if value:
            total += float(value)
    return total