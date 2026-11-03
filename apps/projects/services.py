"""Write operations that touch several records or need history/audit."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.models import AuditLog

from .models import HandoverStatus, ProgressUpdate, Project, SalesHandover, TaskStatus


@transaction.atomic
def change_task_status(task, new_status, user, note="", percent=None):
    """Change a task's status and always leave a ProgressUpdate behind."""
    before = audit.snapshot(task)
    old_status = task.status
    task.status = new_status
    if new_status == TaskStatus.DONE:
        task.completed_at = task.completed_at or timezone.now()
    else:
        task.completed_at = None
    task.updated_by = user
    task.save()

    if not note:
        note = f"Đổi trạng thái: {TaskStatus(old_status).label} → {TaskStatus(new_status).label}"
    update = ProgressUpdate.objects.create(
        project=task.project,
        task=task,
        author=user,
        percent=percent,
        note=note,
        status_from=old_status,
        status_to=new_status,
    )
    changes = audit.diff(before, audit.snapshot(task))
    if changes:
        audit.record(user, task, AuditLog.Action.UPDATE, changes)
    return update


@transaction.atomic
def review_handover(handover, user, status, note):
    # Query instead of handover.linked_project: Django caches a missing
    # reverse one-to-one on the instance, which may be stale here.
    if Project.objects.filter(handover=handover).exists():
        raise ValidationError("Bàn giao đã được dùng để tạo dự án, không thể đổi trạng thái tiếp nhận.")
    before = audit.snapshot(handover)
    handover.status = status
    handover.review_note = note
    handover.reviewed_by = user
    handover.reviewed_at = timezone.now()
    handover.updated_by = user
    handover.save()
    audit.record(user, handover, AuditLog.Action.UPDATE, audit.diff(before, audit.snapshot(handover)))
    return handover


@transaction.atomic
def create_project_from_handover(handover, user, project):
    """Save `project` (unsaved) linked to an ACCEPTED handover.

    A handover can produce at most one project; the OneToOne field is the
    database-level guard and the lock prevents a double submit race.
    """
    handover = SalesHandover.objects.select_for_update().get(pk=handover.pk)
    if handover.status != HandoverStatus.ACCEPTED:
        raise ValidationError("Chỉ tạo dự án từ bàn giao đã được chấp nhận.")
    if Project.objects.filter(handover=handover).exists():
        raise ValidationError("Bàn giao này đã có dự án.")
    project.handover = handover
    project.is_demo_data = handover.is_demo_data
    project.created_by = project.updated_by = user
    project.save()
    audit.record(user, project, AuditLog.Action.CREATE, audit.snapshot(project))
    return project
