# bus_station/templatetags/math_filters.py
from django import template

register = template.Library()

@register.filter
def sum_attr(queryset, attr):
    return sum(getattr(item, attr, 0) for item in queryset)