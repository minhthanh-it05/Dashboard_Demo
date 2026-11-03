"""Shared output for sync management commands."""

from django.core.management.base import CommandError

from .models import SyncStatus


def report_runs(command, runs):
    """Print one line per run; fail the command if any run failed."""
    for run in runs:
        style = {
            SyncStatus.SUCCESS: command.style.SUCCESS,
            SyncStatus.PARTIAL: command.style.WARNING,
        }.get(run.status, command.style.ERROR)
        label = " [MÔ PHỎNG]" if run.is_simulated else ""
        command.stdout.write(
            style(
                f"{run.get_system_display()} / {run.entity}{label}: {run.get_status_display()} — "
                f"đọc {run.fetched}, tạo {run.created}, cập nhật {run.updated}, "
                f"không đổi {run.unchanged}, lỗi {run.failed}. {run.message}"
            )
        )
        for warning in run.warnings:
            command.stdout.write(command.style.WARNING(f"  ! {warning['ref']}: {warning['message']}"))
    if any(run.status == SyncStatus.FAILED for run in runs):
        raise CommandError("Có lượt đồng bộ thất bại.")
