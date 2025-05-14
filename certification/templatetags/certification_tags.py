from django import template

register = template.Library()

@register.filter
def filter_by_user(queryset, user):
    """Filter a queryset by user"""
    return queryset.filter(user=user) 