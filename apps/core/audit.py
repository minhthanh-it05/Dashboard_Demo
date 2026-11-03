"""Small helpers for recording who changed what (CLAUDE.md §7.3)."""

import datetime

from django.contrib.contenttypes.models import ContentType

from .models import AuditLog

IGNORED_FIELDS = {"created_at", "updated_at", "created_by", "updated_by"}


def _to_json(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, datetime.date):  # also covers datetime
        return value.isoformat()
    return str(value)  # Decimal, UUID


def snapshot(instance):
    """Return the instance's concrete field values as JSON-safe data."""
    return {
        field.name: _to_json(field.value_from_object(instance))
        for field in instance._meta.concrete_fields
        if field.name not in IGNORED_FIELDS
    }


def diff(before, after):
    return {
        name: {"old": before.get(name), "new": value}
        for name, value in after.items()
        if before.get(name) != value
    }


def record(actor, instance, action, changes=None):
    return AuditLog.objects.create(
        actor=actor if actor is not None and actor.is_authenticated else None,
        action=action,
        content_type=ContentType.objects.get_for_model(instance),
        object_id=str(instance.pk),
        object_repr=str(instance)[:255],
        changes=changes or {},
    )
