from dataclasses import asdict

from django.db import transaction

from apps.integrations.records import duplicate_keys

from .models import ROW_MODELS, FinanceImportBatch, ImportStatus


class SnapshotRejected(ValueError):
    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def validate_rows(rows):
    """Return a list of error messages for a set of normalized records."""
    if not rows:
        return ["Không có dòng dữ liệu nào."]
    duplicates = duplicate_keys(rows)
    if duplicates:
        keys = ", ".join(sorted(str(key) for key in duplicates))
        return [f"Trùng khoá trong cùng một lô: {keys}"]
    return []


@transaction.atomic
def store_snapshot(*, data_kind, source_system, as_of_date, rows, **batch_fields):
    """Save `rows` as the new current snapshot for `data_kind` (all-or-nothing)."""
    errors = validate_rows(rows)
    if errors:
        raise SnapshotRejected(errors)

    batch = FinanceImportBatch.objects.create(
        data_kind=data_kind,
        source_system=source_system,
        as_of_date=as_of_date,
        status=ImportStatus.IMPORTED,
        row_count=len(rows),
        **batch_fields,
    )
    row_model = ROW_MODELS[data_kind]
    row_model.objects.bulk_create([row_model(batch=batch, **asdict(row)) for row in rows])

    FinanceImportBatch.objects.filter(data_kind=data_kind, is_current=True).update(is_current=False)
    batch.is_current = True
    batch.save(update_fields=["is_current"])
    return batch


def record_rejected(*, data_kind, source_system, as_of_date, errors, **batch_fields):
    """Keep a history row for a rejected import; no data rows are stored."""
    return FinanceImportBatch.objects.create(
        data_kind=data_kind,
        source_system=source_system,
        as_of_date=as_of_date,
        status=ImportStatus.REJECTED,
        errors=errors,
        **batch_fields,
    )


def current_batch(data_kind):
    return FinanceImportBatch.objects.filter(data_kind=data_kind, is_current=True).first()
