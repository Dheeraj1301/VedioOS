from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def money(amount, currency):
    if amount is None:
        return "Not configured"
    decimals = 0 if currency in {"JPY", "KRW"} else 2
    return f"{currency} {Decimal(amount) / (10**decimals):,.{decimals}f}"
