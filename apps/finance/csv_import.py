"""Import finance reports from CSV using the PROPOSED templates below.

The real reports Accounting can export are not known yet
(docs/OPEN_QUESTIONS.md, section E), so these columns are our proposal and
must be agreed with Accounting before use. Sample files: docs/samples/.

Rules: UTF-8 (BOM allowed), comma separated, header row required, numbers
use "." as decimal separator and no thousands separators. A file is imported
completely or not at all.
"""

import csv
import hashlib
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Callable

from apps.core.models import SourceSystem
from apps.integrations.records import DebtBalanceRecord, InventoryBalanceRecord

from . import services
from .models import FinanceDataKind, FinanceImportBatch, ImportStatus

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
MAX_REPORTED_ERRORS = 50


def _text(row, name, required=False):
    value = (row.get(name) or "").strip()
    if required and not value:
        raise ValueError(f"thiếu giá trị cột '{name}'")
    return value


def _decimal(row, name, required=False):
    value = _text(row, name, required)
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError(f"cột '{name}' không phải số hợp lệ: {value!r}") from None


def _debt_record(row):
    return DebtBalanceRecord(
        counterparty_code=_text(row, "counterparty_code", required=True),
        counterparty_name=_text(row, "counterparty_name", required=True),
        receivable_amount=_decimal(row, "receivable_amount"),
        payable_amount=_decimal(row, "payable_amount"),
        currency=_text(row, "currency") or "VND",
    )


def _inventory_record(row):
    return InventoryBalanceRecord(
        item_code=_text(row, "item_code", required=True),
        item_name=_text(row, "item_name", required=True),
        warehouse_code=_text(row, "warehouse_code", required=True),
        quantity=_decimal(row, "quantity", required=True),
        unit=_text(row, "unit"),
        amount=_decimal(row, "amount"),
    )


@dataclass(frozen=True)
class CsvTemplate:
    columns: tuple
    build: Callable


TEMPLATES = {
    FinanceDataKind.DEBT_BALANCE: CsvTemplate(
        columns=("counterparty_code", "counterparty_name", "receivable_amount", "payable_amount", "currency"),
        build=_debt_record,
    ),
    FinanceDataKind.INVENTORY_BALANCE: CsvTemplate(
        columns=("item_code", "item_name", "warehouse_code", "quantity", "unit", "amount"),
        build=_inventory_record,
    ),
}


@dataclass
class ParseResult:
    records: list
    errors: list


def parse(raw_bytes, data_kind):
    template = TEMPLATES[data_kind]
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ParseResult([], ["File không phải mã hoá UTF-8."])

    reader = csv.DictReader(io.StringIO(text))
    missing = [name for name in template.columns if name not in (reader.fieldnames or [])]
    if missing:
        return ParseResult([], [f"Thiếu cột: {', '.join(missing)}. Cột yêu cầu: {', '.join(template.columns)}."])

    records, errors = [], []
    for line_number, row in enumerate(reader, start=2):
        if line_number - 1 > MAX_ROWS:
            errors.append(f"File vượt quá {MAX_ROWS} dòng dữ liệu.")
            break
        try:
            records.append(template.build(row))
        except ValueError as exc:
            errors.append(f"Dòng {line_number}: {exc}")
    return ParseResult(records, errors)


def import_file(raw_bytes, *, filename, data_kind, as_of_date, user, period_label=""):
    """Validate and import one CSV file; always returns the history batch."""
    batch_fields = {
        "data_kind": data_kind,
        "source_system": SourceSystem.FINANCE_CSV,
        "as_of_date": as_of_date,
        "source_filename": filename,
        "file_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "period_label": period_label,
        "imported_by": user,
    }
    if len(raw_bytes) > MAX_FILE_BYTES:
        return services.record_rejected(errors=[f"File lớn hơn {MAX_FILE_BYTES // 1024} KB."], **batch_fields)
    if FinanceImportBatch.objects.filter(
        data_kind=data_kind, file_sha256=batch_fields["file_sha256"], status=ImportStatus.IMPORTED
    ).exists():
        return services.record_rejected(errors=["File có nội dung trùng với một lần nhập trước đó."], **batch_fields)

    result = parse(raw_bytes, data_kind)
    if result.errors:
        return services.record_rejected(errors=result.errors[:MAX_REPORTED_ERRORS], **batch_fields)
    try:
        return services.store_snapshot(rows=result.records, **batch_fields)
    except services.SnapshotRejected as exc:
        return services.record_rejected(errors=exc.errors, **batch_fields)
