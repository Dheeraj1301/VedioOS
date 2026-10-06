from django import template

from core.money import format_money

register = template.Library()


@register.filter
def money(amount, currency):
    return format_money(amount, currency)
