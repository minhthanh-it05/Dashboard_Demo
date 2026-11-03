from functools import partial

from django.utils import timezone

from apps.core.models import SourceSystem
from apps.integrations.exceptions import ResponseFormatError
from apps.integrations.misa.provider import get_provider
from apps.integrations.models import ExternalSystem, SyncMode
from apps.integrations.runner import run_sync

from . import services
from .models import FinanceDataKind

# entity -> (finance data kind, provider method)
ENTITIES = {
    "debt_balances": (FinanceDataKind.DEBT_BALANCE, "fetch_debt_balances"),
    "inventory_balances": (FinanceDataKind.INVENTORY_BALANCE, "fetch_inventory_balances"),
}


def _sync_snapshot(provider, data_kind, fetch_method, context):
    """Fetch a full snapshot and make it current. Safe to re-run: the newer
    batch supersedes the older one instead of adding rows to it."""
    records = getattr(provider, fetch_method)()
    context.stats.fetched = len(records)
    try:
        services.store_snapshot(
            data_kind=data_kind,
            source_system=SourceSystem.MISA_ACT_API,
            as_of_date=timezone.localdate(),
            rows=records,
            is_simulated=provider.mode == SyncMode.MOCK,
            sync_run=context.run,
            imported_by=context.run.triggered_by,
        )
    except services.SnapshotRejected as exc:
        raise ResponseFormatError(f"Dữ liệu nhận được không hợp lệ, không nhập: {exc}") from exc
    context.stats.created = len(records)
    return ""  # full snapshots: no incremental cursor yet


def run_misa_sync(entities=tuple(ENTITIES), user=None):
    provider = get_provider()
    runs = []
    for entity, (data_kind, fetch_method) in ENTITIES.items():
        if entity in entities:
            sync_fn = partial(_sync_snapshot, provider, data_kind, fetch_method)
            runs.append(run_sync(ExternalSystem.MISA_ACT, entity, provider.mode, sync_fn, user=user))
    return runs
