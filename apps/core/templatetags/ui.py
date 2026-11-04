import os
from decimal import Decimal

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()

BADGE_CLASSES = {
    # projects
    "PENDING_HANDOVER": "secondary",
    "READY": "info",
    "IN_PROGRESS": "primary",
    "ON_HOLD": "warning",
    "COMPLETED": "success",
    "CANCELLED": "dark",
    # handovers
    "PENDING": "secondary",
    "NEEDS_INFO": "warning",
    "ACCEPTED": "success",
    "REJECTED": "danger",
    # milestones / tasks / issues
    "PLANNED": "secondary",
    "TODO": "secondary",
    "BLOCKED": "danger",
    "DONE": "success",
    "OPEN": "danger",
    "RESOLVED": "success",
    "CLOSED": "dark",
    # severity / priority
    "LOW": "secondary",
    "MEDIUM": "info",
    "HIGH": "warning",
    "CRITICAL": "danger",
}


@register.filter
def badge(value):
    return BADGE_CLASSES.get(str(value), "secondary")


@register.filter
def days_from(value, reference):
    """Whole days from `reference` to `value` (negative = in the past).

    Used instead of Django's timesince/timeuntil, whose output mixes units
    ("1 week, 1 day") and is not fully translated to Vietnamese.
    """
    if not value or not reference:
        return None
    return (value - reference).days


@register.simple_tag
def asset(path):
    """Static URL versioned by the file's modification time.

    The URL changes whenever the file does, so browsers never keep an old
    stylesheet or script after an update (no hard refresh needed).
    """
    url = static(path)
    found = finders.find(path)
    return f"{url}?v={int(os.path.getmtime(found))}" if found else url


@register.simple_tag(takes_context=True)
def query_with(context, **params):
    """Current query string with `params` replaced (keeps filters when paging)."""
    query = context["request"].GET.copy()
    for name, value in params.items():
        query[name] = value
    return query.urlencode()


@register.filter
def money(value, currency=""):
    if value is None or value == "":
        return "—"
    value = Decimal(value)
    places = 0 if currency in ("", "VND") else 2
    formatted = f"{value:,.{places}f}".replace(",", ".") if places == 0 else f"{value:,.{places}f}"
    return f"{formatted} {currency}".strip()
