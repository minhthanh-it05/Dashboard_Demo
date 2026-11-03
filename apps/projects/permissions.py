"""Object-level access rules. Every project-scoped view goes through these.

Policy (Phase 1 assumption, see docs/OPEN_QUESTIONS.md):
- Project managers see and manage all projects.
- Other users see only projects they are a member (or manager) of.
- Members may update their own tasks, post progress, and raise issues.
"""

from django.db.models import Q

from apps.accounts.roles import is_project_manager

from .models import Project


def visible_projects(user):
    if not user.is_authenticated:
        return Project.objects.none()
    if is_project_manager(user):
        return Project.objects.all()
    return Project.objects.filter(Q(members__user=user) | Q(manager=user)).distinct()


def can_manage_project(user, project):
    return is_project_manager(user)


def can_update_task(user, task):
    return can_manage_project(user, task.project) or task.assignee_id == user.pk


def can_edit_issue(user, issue):
    return can_manage_project(user, issue.project) or user.pk in (issue.assignee_id, issue.reported_by_id)


def project_participants(project):
    """Users who can be assigned work on the project: members + manager."""
    from django.contrib.auth import get_user_model

    return (
        get_user_model()
        .objects.filter(Q(project_memberships__project=project) | Q(managed_projects=project))
        .distinct()
        .order_by("username")
    )
