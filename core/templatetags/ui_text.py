from django import template


register = template.Library()


@register.filter
def without_link_arrows(value):
    """Hide legacy decorative arrows while preserving the linked action."""
    return str(value or "").replace("↗", "").replace("→", "").strip()
