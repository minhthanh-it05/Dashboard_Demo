"""OplaCRM provider contract and factory.

A provider yields normalized records (apps.integrations.records). Sync
services depend only on this contract, never on a concrete provider.
"""

from typing import Iterable, Protocol

from django.conf import settings

from apps.integrations import modes
from apps.integrations.records import AccountRecord, OpportunityRecord


class OplaCRMProvider(Protocol):
    mode: str  # SyncMode value

    def iter_accounts(self, updated_since) -> Iterable[AccountRecord]: ...

    def iter_opportunities(self, updated_since) -> Iterable[OpportunityRecord]: ...


def get_provider():
    from .live import LiveOplaCRMProvider
    from .mock import MockOplaCRMProvider

    return modes.resolve(
        "OPLACRM_MODE",
        settings.OPLACRM_MODE,
        mock_factory=MockOplaCRMProvider,
        live_factory=LiveOplaCRMProvider.from_settings,
    )
