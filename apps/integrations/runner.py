"""Generic sync execution: bookkeeping, error capture and cursor handling.

Domain apps provide a `sync_fn(context)` that fetches records, upserts them
and returns the new cursor; this module records the run either way.
"""

import logging
from dataclasses import dataclass, field

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .exceptions import IntegrationError
from .models import SyncRun, SyncState, SyncStatus

logger = logging.getLogger(__name__)

MAX_STORED_MESSAGES = 50

CREATED, UPDATED, UNCHANGED = "created", "updated", "unchanged"


@dataclass
class SyncStats:
    fetched: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def count(self, outcome):
        setattr(self, outcome, getattr(self, outcome) + 1)

    def record_error(self, ref, message):
        self.failed += 1
        if len(self.errors) < MAX_STORED_MESSAGES:
            self.errors.append({"ref": str(ref), "message": message})

    def record_warning(self, ref, message):
        if len(self.warnings) < MAX_STORED_MESSAGES:
            self.warnings.append({"ref": str(ref), "message": message})


@dataclass
class SyncContext:
    run: SyncRun
    cursor: str
    stats: SyncStats


def run_sync(system, entity, mode, sync_fn, *, user=None):
    state, _ = SyncState.objects.get_or_create(system=system, entity=entity)
    run = SyncRun.objects.create(system=system, entity=entity, mode=mode, triggered_by=user)
    context = SyncContext(run=run, cursor=state.cursor, stats=SyncStats())

    try:
        new_cursor = sync_fn(context)
    except IntegrationError as exc:
        logger.warning("Sync %s/%s failed: %s", system, entity, exc)
        _finish(run, context.stats, SyncStatus.FAILED, str(exc))
    except Exception:
        logger.exception("Sync %s/%s crashed", system, entity)
        _finish(run, context.stats, SyncStatus.FAILED, "Lỗi không mong đợi; xem log máy chủ.")
    else:
        status = SyncStatus.PARTIAL if context.stats.failed else SyncStatus.SUCCESS
        _finish(run, context.stats, status, "")
        if status == SyncStatus.SUCCESS:
            state.cursor = new_cursor or state.cursor
            state.last_success_at = run.finished_at

    state.last_run = run
    state.save()
    return run


def _finish(run, stats, status, message):
    run.status = status
    run.message = message
    run.finished_at = timezone.now()
    for name in ("fetched", "created", "updated", "unchanged", "failed", "errors", "warnings"):
        setattr(run, name, getattr(stats, name))
    run.save()


def upsert(model, *, lookup, values, touch=None):
    """Create or update one row; write only when a value actually changed.

    `touch` fields (e.g. last_synced_at) are written on create/update but are
    not compared, so an unchanged source record stays UNCHANGED.
    Returns (instance, outcome).
    """
    touch = touch or {}
    instance = model.objects.filter(**lookup).first()
    if instance is None:
        return model.objects.create(**lookup, **values, **touch), CREATED

    changed = [name for name, value in values.items() if getattr(instance, name) != value]
    if not changed:
        return instance, UNCHANGED
    for name in changed:
        setattr(instance, name, values[name])
    for name, value in touch.items():
        setattr(instance, name, value)
    instance.save(update_fields=[*changed, *touch])
    return instance, UPDATED


def cursor_to_datetime(cursor):
    return parse_datetime(cursor) if cursor else None


def datetime_to_cursor(value):
    return value.isoformat() if value else ""
