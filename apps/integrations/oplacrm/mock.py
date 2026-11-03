from apps.integrations import simulated
from apps.integrations.models import SyncMode
from apps.integrations.records import AccountRecord, OpportunityRecord

DATA_FILE = "oplacrm_simulated.json"


class MockOplaCRMProvider:
    """Serves SIMULATED records from a bundled simulated data file (no network)."""

    mode = SyncMode.MOCK

    def __init__(self, data=None):
        self._data = data if data is not None else simulated.load(DATA_FILE)

    def iter_accounts(self, updated_since):
        for row in self._data["accounts"]:
            record = AccountRecord(
                external_id=row["external_id"],
                name=row["name"],
                updated_at=simulated.to_datetime(row.get("updated_at")),
            )
            if _is_newer(record.updated_at, updated_since):
                yield record

    def iter_opportunities(self, updated_since):
        for row in self._data["opportunities"]:
            record = OpportunityRecord(
                external_id=row["external_id"],
                name=row["name"],
                account_external_id=row.get("account_external_id", ""),
                amount=simulated.to_decimal(row.get("amount")),
                currency=row.get("currency", "VND"),
                stage_name=row.get("stage_name", ""),
                is_won=row.get("is_won", False),
                expected_close_date=simulated.to_date(row.get("expected_close_date")),
                owner_name=row.get("owner_name", ""),
                updated_at=simulated.to_datetime(row.get("updated_at")),
            )
            if _is_newer(record.updated_at, updated_since):
                yield record


def _is_newer(updated_at, since):
    return since is None or updated_at is None or updated_at > since
