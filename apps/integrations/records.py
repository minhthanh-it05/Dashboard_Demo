"""Normalized records exchanged between adapters/importers and domain apps.

These are OUR internal shapes, not vendor schemas. Live adapters must map
vendor responses into them once the vendor schema is confirmed; domain apps
(sales, finance) only ever see these records.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class AccountRecord:
    external_id: str
    name: str
    updated_at: datetime | None = None


@dataclass(frozen=True)
class OpportunityRecord:
    external_id: str
    name: str
    account_external_id: str = ""
    amount: Decimal | None = None
    currency: str = "VND"
    stage_name: str = ""
    is_won: bool = False
    expected_close_date: date | None = None
    owner_name: str = ""
    updated_at: datetime | None = None


@dataclass(frozen=True)
class DebtBalanceRecord:
    """Balance per counterparty (customer/supplier) — NOT per project."""

    counterparty_code: str
    counterparty_name: str
    receivable_amount: Decimal | None = None
    payable_amount: Decimal | None = None
    currency: str = "VND"

    @property
    def key(self):
        return self.counterparty_code


@dataclass(frozen=True)
class InventoryBalanceRecord:
    item_code: str
    item_name: str
    warehouse_code: str
    quantity: Decimal
    unit: str = ""
    amount: Decimal | None = None

    @property
    def key(self):
        return (self.item_code, self.warehouse_code)


def duplicate_keys(records):
    seen, duplicates = set(), set()
    for record in records:
        if record.key in seen:
            duplicates.add(record.key)
        seen.add(record.key)
    return duplicates
