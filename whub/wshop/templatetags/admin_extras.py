from django import template

register = template.Library()


@register.filter
def intcomma(value):
    try:
        value = int(value)
        return f"{value:,}"
    except (TypeError, ValueError):
        return value


@register.simple_tag
def money(value):
    try:
        return f"${float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"
