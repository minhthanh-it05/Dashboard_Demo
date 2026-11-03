"""Read-only aggregations over the operational data.

The time windows and the "at risk" rule below are demo rules, not approved
business definitions; they are labelled as such in the templates.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F, Max, Q
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.roles import is_project_manager
from apps.payments.models import PaymentRequest
from apps.procurement.models import PurchaseRequest
from apps.projects.models import (
    CLOSED_PROJECT_STATUSES,
    OPEN_ISSUE_STATUSES,
    OPEN_TASK_STATUSES,
    HandoverStatus,
    MilestoneStatus,
    ProgressUpdate,
    Project,
    ProjectIssue,
    ProjectMilestone,
    ProjectStatus,
    ProjectTask,
    SalesHandover,
    Severity,
    TaskStatus,
)
from apps.projects.permissions import visible_projects
from apps.projects.views import PMRequiredMixin, latest_project_percent

UPCOMING_MILESTONE_DAYS = 14
UPCOMING_TASK_DAYS = 7
STALE_PROGRESS_DAYS = 7


@login_required
def home(request):
    if is_project_manager(request.user):
        return redirect("dashboard:pm")
    return redirect("dashboard:my_work")


def _open_tracked(queryset):
    """Open requests, least recently updated first, so stale ones surface."""
    return (
        queryset.filter(tracking_closed=False)
        .exclude(project__status__in=CLOSED_PROJECT_STATUSES)
        .select_related("project")
        .prefetch_related("status_entries")
        .annotate(last_status_at=Max("status_entries__recorded_at"))
        .order_by(F("last_status_at").asc(nulls_first=True))[:10]
    )


class PMDashboardView(PMRequiredMixin, TemplateView):
    template_name = "dashboard/pm_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        counts = dict(Project.objects.values_list("status").annotate(n=Count("id")))
        status_rows = [(value, label, counts.get(value, 0)) for value, label in ProjectStatus.choices]

        active = Project.objects.exclude(status__in=CLOSED_PROJECT_STATUSES)
        overdue_task_q = Q(tasks__status__in=OPEN_TASK_STATUSES, tasks__due_date__lt=today)
        serious_issue_q = Q(
            issues__status__in=OPEN_ISSUE_STATUSES, issues__severity__in=(Severity.HIGH, Severity.CRITICAL)
        )
        at_risk = (
            active.filter(Q(planned_end_date__lt=today) | overdue_task_q | serious_issue_q)
            .distinct()
            .select_related("manager")
            .annotate(latest_percent=latest_project_percent())
        )

        context.update(
            today=today,
            total_projects=sum(counts.values()),
            status_rows=status_rows,
            chart_data={
                "labels": [label for _, label, _ in status_rows],
                "counts": [n for _, _, n in status_rows],
            },
            at_risk_projects=at_risk,
            overdue_tasks=ProjectTask.objects.filter(status__in=OPEN_TASK_STATUSES, due_date__lt=today)
            .select_related("project", "assignee")
            .order_by("due_date")[:20],
            upcoming_milestones=ProjectMilestone.objects.filter(
                status__in=(MilestoneStatus.PLANNED, MilestoneStatus.IN_PROGRESS),
                due_date__gte=today,
                due_date__lte=today + timedelta(days=UPCOMING_MILESTONE_DAYS),
            )
            .exclude(project__status__in=CLOSED_PROJECT_STATUSES)
            .select_related("project")
            .order_by("due_date"),
            upcoming_milestone_days=UPCOMING_MILESTONE_DAYS,
            open_issues=ProjectIssue.objects.filter(status__in=OPEN_ISSUE_STATUSES)
            .select_related("project", "assignee")
            .order_by("-created_at")[:15],
            recent_updates=ProgressUpdate.objects.select_related("project", "task", "author")[:10],
            pending_handovers=SalesHandover.objects.filter(
                status__in=(HandoverStatus.PENDING, HandoverStatus.NEEDS_INFO)
            ),
            open_purchases=_open_tracked(PurchaseRequest.objects.all()),
            open_payments=_open_tracked(PaymentRequest.objects.all()),
        )
        return context


class MyWorkView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard/my_work.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.localdate()
        visible = visible_projects(user)

        my_tasks = list(
            ProjectTask.objects.filter(assignee=user, status__in=OPEN_TASK_STATUSES, project__in=visible)
            .select_related("project", "milestone")
            .annotate(last_update_at=Max("progress_updates__created_at"))
            .order_by(F("due_date").asc(nulls_last=True))
        )
        stale_before = timezone.now() - timedelta(days=STALE_PROGRESS_DAYS)
        upcoming_until = today + timedelta(days=UPCOMING_TASK_DAYS)

        context.update(
            today=today,
            my_projects=Project.objects.filter(Q(members__user=user) | Q(manager=user))
            .distinct()
            .select_related("manager")
            .annotate(latest_percent=latest_project_percent()),
            my_tasks=my_tasks,
            overdue_tasks=[t for t in my_tasks if t.is_overdue],
            upcoming_tasks=[t for t in my_tasks if t.due_date and today <= t.due_date <= upcoming_until],
            stale_tasks=[
                t
                for t in my_tasks
                if t.status == TaskStatus.IN_PROGRESS and (t.last_update_at is None or t.last_update_at < stale_before)
            ],
            my_issues=ProjectIssue.objects.filter(assignee=user, status__in=OPEN_ISSUE_STATUSES, project__in=visible)
            .select_related("project"),
            upcoming_task_days=UPCOMING_TASK_DAYS,
            stale_progress_days=STALE_PROGRESS_DAYS,
        )
        return context
