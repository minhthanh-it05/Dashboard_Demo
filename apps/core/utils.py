from django.utils import timezone


def next_sequential_code(model, field, prefix):
    """Return the next code like PRJ-2026-001 for the current year.

    Not concurrency-safe on its own; the field's unique constraint is the
    final guard. Good enough for the demo, revisit if volume grows.
    """
    stem = f"{prefix}-{timezone.localdate().year}-"
    existing = model.objects.filter(**{f"{field}__startswith": stem}).values_list(field, flat=True)
    numbers = [int(code[len(stem):]) for code in existing if code[len(stem):].isdigit()]
    return f"{stem}{max(numbers, default=0) + 1:03d}"
