"""Read-only aggregations over the operational data.

The time windows and the "needs attention" rule are demo rules, not approved
business definitions; they are labelled as such in the templates.
"""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Max, Q
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from apps.accounts.roles import is_project_manager
from apps.projects.models import (
    OPEN_ISSUE_STATUSES,
    OPEN_TASK_STATUSES,
    HandoverStatus,
    Project,
    ProjectIssue,
    ProjectTask,
    SalesHandover,
    TaskStatus,
)
from apps.projects.permissions import visible_projects
from apps.projects.views import PMRequiredMixin, latest_project_percent

from . import overview

UPCOMING_TASK_DAYS = 7
STALE_PROGRESS_DAYS = 7


@login_required
def home(request):
    if is_project_manager(request.user):
        return redirect("dashboard:pm")
    return redirect("dashboard:my_work")


class PMDashboardView(PMRequiredMixin, TemplateView):
    template_name = "dashboard/pm_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()

        health = overview.project_health(today)
        overdue_tasks = overview.overdue_tasks(today)
        serious_issues = overview.serious_issues()
        milestones = overview.upcoming_milestones(today)
        pending_handovers = SalesHandover.objects.filter(status__in=(HandoverStatus.PENDING, HandoverStatus.NEEDS_INFO))

        context.update(
            today=today,
            kpis={
                "active_projects": len(health),
                "total_projects": Project.objects.count(),
                "needs_attention": sum(row.needs_attention for row in health),
                "overdue_tasks": overdue_tasks.count(),
                "open_tasks": sum(row.open_tasks for row in health),
                "pending_handovers": pending_handovers.count(),
                "handovers_needing_info": pending_handovers.filter(status=HandoverStatus.NEEDS_INFO).count(),
            },
            project_health=health,
            task_mix_chart=overview.task_mix_by_project(),
            due_load_chart=overview.open_tasks_by_due_window(today),
            action_tasks=overdue_tasks.select_related("project", "assignee").order_by("due_date")[
                : overview.MAX_ACTION_TASKS
            ],
            action_issues=serious_issues.select_related("project", "assignee")[: overview.MAX_ACTION_ISSUES],
            serious_issue_count=serious_issues.count(),
            upcoming_milestones=milestones[: overview.MAX_MILESTONES],
            upcoming_milestone_count=milestones.count(),
            upcoming_milestone_days=overview.UPCOMING_MILESTONE_DAYS,
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
