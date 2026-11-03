from decimal import Decimal

from apps.integrations import simulated
from apps.integrations.models import SyncMode
from apps.integrations.records import DebtBalanceRecord, InventoryBalanceRecord

DATA_FILE = "misa_simulated.json"


class MockMisaProvider:
    """Serves SIMULATED balances from a bundled simulated data file (no network)."""

    mode = SyncMode.MOCK

    def __init__(self, data=None):
        self._data = data if data is not None else simulated.load(DATA_FILE)

    def fetch_debt_balances(self):
        return [
            DebtBalanceRecord(
                counterparty_code=row["counterparty_code"],
                counterparty_name=row["counterparty_name"],
                receivable_amount=simulated.to_decimal(row.get("receivable_amount")),
                payable_amount=simulated.to_decimal(row.get("payable_amount")),
                currency=row.get("currency", "VND"),
            )
            for row in self._data["debt_balances"]
        ]

    def fetch_inventory_balances(self):
        return [
            InventoryBalanceRecord(
                item_code=row["item_code"],
                item_name=row["item_name"],
                warehouse_code=row["warehouse_code"],
                quantity=Decimal(str(row["quantity"])),
                unit=row.get("unit", ""),
                amount=simulated.to_decimal(row.get("amount")),
            )
            for row in self._data["inventory_balances"]
        ]
