# bus_station/templatetags/__init__.py
# (порожній файл)

# bus_station/templatetags/bus_filters.py
from django import template

register = template.Library()

@register.filter
def sum_attr(queryset, attr):
    """Сума значень атрибута в queryset"""
    return sum(getattr(item, attr, 0) for item in queryset)

@register.filter
def percentage(value, total):
    """Розрахувати відсоток"""
    if total == 0:
        return 0
    return (value / total) * 100