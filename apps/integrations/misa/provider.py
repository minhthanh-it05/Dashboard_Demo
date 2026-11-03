"""MISA provider contract and factory.

Balances are fetched as full snapshots. Incremental sync (last_sync_time and
the *_delete endpoints) is left for when the vendor confirms its behaviour.
"""

from typing import Protocol

from django.conf import settings

from apps.integrations import modes
from apps.integrations.records import DebtBalanceRecord, InventoryBalanceRecord


class MisaProvider(Protocol):
    mode: str  # SyncMode value

    def fetch_debt_balances(self) -> list[DebtBalanceRecord]: ...

    def fetch_inventory_balances(self) -> list[InventoryBalanceRecord]: ...


def get_provider():
    from .live import LiveMisaProvider
    from .mock import MockMisaProvider

    return modes.resolve(
        "MISA_MODE",
        settings.MISA_MODE,
        mock_factory=MockMisaProvider,
        live_factory=LiveMisaProvider.from_settings,
    )
