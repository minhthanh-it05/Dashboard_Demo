"""Map OplaCRM records into the Sales read model and pending handovers.

Ownership rules (CLAUDE.md §3.4, §9 Phase 2):
- Accounts/opportunities are Sales-owned and mirrored as-is.
- A won opportunity creates a PENDING SalesHandover, never a Project.
- Handover `committed_*` fields follow the opportunity only while Project has
  not decided on the handover. After that, differences are reported as
  warnings and not applied (assumption, see docs/OPEN_QUESTIONS.md).
"""

from django.db import DatabaseError, transaction
from django.utils import timezone

from apps.core import audit
from apps.core.models import AuditLog, SourceSystem
from apps.integrations.models import SyncMode
from apps.integrations.runner import UPDATED, cursor_to_datetime, datetime_to_cursor, upsert
from apps.projects.models import HandoverStatus, SalesHandover

from .models import SalesAccount, SalesOpportunity

OPEN_HANDOVER_STATUSES = (HandoverStatus.PENDING, HandoverStatus.NEEDS_INFO)


class InvalidRecord(ValueError):
    pass


def sync_accounts(provider, context):
    return _sync_records(provider.iter_accounts, _save_account, provider.mode, context)


def sync_opportunities(provider, context):
    return _sync_records(provider.iter_opportunities, _save_opportunity, provider.mode, context)


def _sync_records(fetch, save, mode, context):
    """Upsert each record in its own savepoint so one bad record does not
    abort the batch. Returns the newest source timestamp as the next cursor."""
    stats = context.stats
    newest = cursor_to_datetime(context.cursor)
    simulated = mode == SyncMode.MOCK

    for record in fetch(newest):
        stats.fetched += 1
        try:
            with transaction.atomic():
                stats.count(save(record, simulated, stats))
        except (InvalidRecord, DatabaseError) as exc:
            stats.record_error(record.external_id, str(exc))
            continue
        if record.updated_at and (newest is None or record.updated_at > newest):
            newest = record.updated_at
    return datetime_to_cursor(newest)


def _require(record, *field_names):
    missing = [name for name in field_names if not getattr(record, name)]
    if missing:
        raise InvalidRecord(f"Thiếu trường bắt buộc: {', '.join(missing)}")


def _save_account(record, simulated, stats):
    _require(record, "external_id", "name")
    _, outcome = upsert(
        SalesAccount,
        lookup={"source_system": SourceSystem.OPLACRM, "external_id": record.external_id},
        values={"name": record.name, "source_updated_at": record.updated_at, "is_simulated": simulated},
        touch={"last_synced_at": timezone.now()},
    )
    return outcome


def _save_opportunity(record, simulated, stats):
    _require(record, "external_id", "name")
    account = SalesAccount.objects.filter(
        source_system=SourceSystem.OPLACRM, external_id=record.account_external_id
    ).first()
    opportunity, outcome = upsert(
        SalesOpportunity,
        lookup={"source_system": SourceSystem.OPLACRM, "external_id": record.external_id},
        values={
            "account": account,
            "account_external_id": record.account_external_id,
            "name": record.name,
            "amount": record.amount,
            "currency": record.currency,
            "stage_name": record.stage_name,
            "is_won": record.is_won,
            "expected_close_date": record.expected_close_date,
            "owner_name": record.owner_name,
            "source_updated_at": record.updated_at,
            "is_simulated": simulated,
        },
        touch={"last_synced_at": timezone.now()},
    )
    if opportunity.is_won:
        _ensure_pending_handover(opportunity, stats)
    return outcome


def _handover_values(opportunity):
    customer = opportunity.account.name if opportunity.account else f"(Chưa đồng bộ khách hàng {opportunity.account_external_id})"
    return {
        "customer_name": customer,
        "deal_name": opportunity.name,
        "external_account_id": opportunity.account_external_id,
        "sales_owner_name": opportunity.owner_name,
        "committed_value": opportunity.amount,
        "currency": opportunity.currency,
    }


def _ensure_pending_handover(opportunity, stats):
    lookup = {"source_system": SourceSystem.OPLACRM, "external_opportunity_id": opportunity.external_id}
    values = _handover_values(opportunity)
    handover = SalesHandover.objects.filter(**lookup).first()

    if handover is None:
        handover = SalesHandover.objects.create(
            **lookup, **values, status=HandoverStatus.PENDING, is_demo_data=opportunity.is_simulated
        )
        audit.record(None, handover, AuditLog.Action.CREATE, audit.snapshot(handover))
        return

    if handover.status in OPEN_HANDOVER_STATUSES:
        before = audit.snapshot(handover)
        handover, outcome = upsert(SalesHandover, lookup=lookup, values=values)
        if outcome == UPDATED:
            audit.record(None, handover, AuditLog.Action.UPDATE, audit.diff(before, audit.snapshot(handover)))
        return

    differing = [name for name, value in values.items() if getattr(handover, name) != value]
    if differing:
        stats.record_warning(
            opportunity.external_id,
            f"Bàn giao đã '{handover.get_status_display()}'; không tự cập nhật các trường: {', '.join(differing)}.",
        )
