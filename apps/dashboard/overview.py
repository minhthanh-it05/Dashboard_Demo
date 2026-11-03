"""Data for the PM overview page.

The overview answers three questions only (inverted pyramid):
1. How is the portfolio doing?            -> KPIs + project health table
2. Where is the work?                     -> task status chart
3. What needs action now / soon?          -> action items + upcoming milestones
Everything else lives on the project, handover and finance pages.

"Needs attention" is a demo rule (docs/OPEN_QUESTIONS.md A13), not an
approved business definition.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Case, Count, IntegerField, Q, When

from apps.projects.models import (
    CLOSED_PROJECT_STATUSES,
    OPEN_ISSUE_STATUSES,
    OPEN_TASK_STATUSES,
    MilestoneStatus,
    Project,
    ProjectIssue,
    ProjectMilestone,
    ProjectTask,
    Severity,
    TaskStatus,
)
from apps.projects.views import latest_project_percent

SERIOUS_SEVERITIES = (Severity.HIGH, Severity.CRITICAL)
UPCOMING_MILESTONE_DAYS = 14
MAX_ACTION_TASKS = 5
MAX_ACTION_ISSUES = 3
MAX_MILESTONES = 6

# Stack order = progression (validated indigo ramp, dark = done) + blocked in red.
TASK_STATUS_SERIES = (
    (TaskStatus.DONE, "task-done"),
    (TaskStatus.IN_PROGRESS, "task-in-progress"),
    (TaskStatus.TODO, "task-todo"),
    (TaskStatus.BLOCKED, "task-blocked"),
)


@dataclass
class ProjectHealth:
    project: Project
    open_tasks: int
    overdue_tasks: int
    serious_issues: int
    reasons: list = field(default_factory=list)

    @property
    def needs_attention(self):
        return bool(self.reasons)


def project_health(today):
    """Open projects with their attention reasons; attention first, then by end date."""
    projects = (
        Project.objects.exclude(status__in=CLOSED_PROJECT_STATUSES)
        .select_related("manager")
        .annotate(
            latest_percent=latest_project_percent(),
            n_open=Count("tasks", filter=Q(tasks__status__in=OPEN_TASK_STATUSES), distinct=True),
            n_overdue=Count(
                "tasks", filter=Q(tasks__status__in=OPEN_TASK_STATUSES, tasks__due_date__lt=today), distinct=True
            ),
            n_serious=Count(
                "issues",
                filter=Q(issues__status__in=OPEN_ISSUE_STATUSES, issues__severity__in=SERIOUS_SEVERITIES),
                distinct=True,
            ),
        )
    )
    rows = []
    for project in projects:
        row = ProjectHealth(project, project.n_open, project.n_overdue, project.n_serious)
        if project.is_overdue:
            row.reasons.append("Quá ngày kết thúc")
        if row.overdue_tasks:
            row.reasons.append(f"{row.overdue_tasks} việc quá hạn")
        if row.serious_issues:
            row.reasons.append(f"{row.serious_issues} vấn đề mức cao")
        rows.append(row)
    far_future = today + timedelta(days=36500)
    rows.sort(key=lambda r: (not r.needs_attention, r.project.planned_end_date or far_future))
    return rows


def task_mix_by_project():
    """Stacked bar: task count per status for each open project."""
    projects = list(
        Project.objects.exclude(status__in=CLOSED_PROJECT_STATUSES)
        .annotate(
            **{f"n_{status}": Count("tasks", filter=Q(tasks__status=status)) for status, _ in TASK_STATUS_SERIES}
        )
        .order_by("code")
    )
    return {
        "labels": [project.code for project in projects],
        "titles": [project.name for project in projects],
        "datasets": [
            {
                "label": TaskStatus(status).label,
                "color": role,
                "data": [getattr(project, f"n_{status}") for project in projects],
            }
            for status, role in TASK_STATUS_SERIES
        ],
    }


def open_tasks_by_due_window(today):
    """Doughnut: open tasks by how soon they are due. Five slices at most, so
    each gets its own colour (overdue red, then an indigo ramp by urgency)."""
    this_week = today - timedelta(days=today.weekday())
    next_week = this_week + timedelta(weeks=1)
    after_next = this_week + timedelta(weeks=2)

    open_tasks = ProjectTask.objects.filter(status__in=OPEN_TASK_STATUSES).exclude(
        project__status__in=CLOSED_PROJECT_STATUSES
    )
    windows = (
        ("Quá hạn", "overdue", Q(due_date__lt=today)),
        ("Tuần này", "due-1", Q(due_date__gte=today, due_date__lt=next_week)),
        ("Tuần sau", "due-2", Q(due_date__gte=next_week, due_date__lt=after_next)),
        ("Từ 2 tuần nữa", "due-3", Q(due_date__gte=after_next)),
        ("Chưa có hạn", "neutral", Q(due_date__isnull=True)),
    )
    counts = open_tasks.aggregate(**{f"w{i}": Count("id", filter=q) for i, (_, _, q) in enumerate(windows)})
    return {
        "labels": [label for label, _, _ in windows],
        "datasets": [
            {
                "label": "Việc đang mở",
                "colors": [role for _, role, _ in windows],
                "data": [counts[f"w{i}"] for i in range(len(windows))],
            }
        ],
    }


def overdue_tasks(today):
    return ProjectTask.objects.filter(status__in=OPEN_TASK_STATUSES, due_date__lt=today).exclude(
        project__status__in=CLOSED_PROJECT_STATUSES
    )


def serious_issues():
    """Open HIGH/CRITICAL issues, CRITICAL first (severity is text, so rank it)."""
    return (
        ProjectIssue.objects.filter(status__in=OPEN_ISSUE_STATUSES, severity__in=SERIOUS_SEVERITIES)
        .exclude(project__status__in=CLOSED_PROJECT_STATUSES)
        .annotate(
            severity_rank=Case(When(severity=Severity.CRITICAL, then=0), default=1, output_field=IntegerField())
        )
        .order_by("severity_rank", "created_at")
    )


def upcoming_milestones(today):
    return (
        ProjectMilestone.objects.filter(
            status__in=(MilestoneStatus.PLANNED, MilestoneStatus.IN_PROGRESS),
            due_date__gte=today,
            due_date__lte=today + timedelta(days=UPCOMING_MILESTONE_DAYS),
        )
        .exclude(project__status__in=CLOSED_PROJECT_STATUSES)
        .select_related("project")
        .order_by("due_date")
    )
