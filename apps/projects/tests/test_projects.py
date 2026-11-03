from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.core.models import AuditLog
from apps.core.testing import TEST_PASSWORD, make_user
from apps.projects import services
from apps.projects.models import (
    HandoverStatus,
    ProgressUpdate,
    Project,
    ProjectContract,
    ProjectIssue,
    ProjectMember,
    ProjectStatus,
    ProjectTask,
    SalesHandover,
    TaskStatus,
)
from apps.projects.permissions import visible_projects


class ProjectTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pm = make_user("pm", roles.PROJECT_MANAGER)
        cls.member = make_user("member", roles.PROJECT_MEMBER)
        cls.other = make_user("other", roles.PROJECT_MEMBER)
        cls.project = Project.objects.create(name="Alpha", customer_name="Cust A", manager=cls.pm)
        cls.hidden = Project.objects.create(name="Beta", customer_name="Cust B", manager=cls.pm)
        ProjectMember.objects.create(project=cls.project, user=cls.member)
        ProjectMember.objects.create(project=cls.hidden, user=cls.other)

    def login(self, user):
        self.client.login(username=user.username, password=TEST_PASSWORD)

    def url(self, name, *args):
        return reverse(f"projects:{name}", args=args)


class VisibilityTests(ProjectTestCase):
    def test_pm_sees_all_projects(self):
        self.assertEqual(set(visible_projects(self.pm)), {self.project, self.hidden})

    def test_member_sees_only_assigned_projects(self):
        self.assertEqual(list(visible_projects(self.member)), [self.project])

    def test_member_gets_404_for_other_project(self):
        self.login(self.member)
        self.assertEqual(self.client.get(self.url("detail", self.hidden.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.url("detail", self.project.pk)).status_code, 200)

    def test_project_list_is_scoped(self):
        self.login(self.member)
        response = self.client.get(self.url("list"))
        self.assertContains(response, "Alpha")
        self.assertNotContains(response, "Beta")

    def test_member_cannot_create_or_edit_projects(self):
        self.login(self.member)
        self.assertEqual(self.client.get(self.url("create")).status_code, 403)
        self.assertEqual(self.client.get(self.url("update", self.project.pk)).status_code, 403)
        self.assertEqual(self.client.get(self.url("task_create", self.project.pk)).status_code, 403)


class ProjectCrudTests(ProjectTestCase):
    def test_project_code_is_generated(self):
        year = timezone.localdate().year
        self.assertEqual(self.project.code, f"PRJ-{year}-001")
        self.assertEqual(self.hidden.code, f"PRJ-{year}-002")

    def test_pm_creates_project_and_audit_is_recorded(self):
        self.login(self.pm)
        response = self.client.post(
            self.url("create"),
            {"name": "Gamma", "customer_name": "Cust G", "status": ProjectStatus.READY, "manager": self.pm.pk},
        )
        project = Project.objects.get(name="Gamma")
        self.assertRedirects(response, project.get_absolute_url())
        self.assertEqual(project.created_by, self.pm)
        self.assertTrue(AuditLog.objects.filter(object_id=str(project.pk), action=AuditLog.Action.CREATE).exists())

    def test_status_change_is_audited(self):
        self.login(self.pm)
        self.client.post(
            self.url("update", self.project.pk),
            {"name": "Alpha", "customer_name": "Cust A", "status": ProjectStatus.ON_HOLD, "manager": self.pm.pk},
        )
        log = AuditLog.objects.get(object_id=str(self.project.pk), action=AuditLog.Action.UPDATE)
        self.assertEqual(log.changes["status"], {"old": ProjectStatus.READY, "new": ProjectStatus.ON_HOLD})
        self.assertEqual(log.actor, self.pm)

    def test_end_before_start_is_rejected(self):
        self.login(self.pm)
        today = timezone.localdate()
        response = self.client.post(
            self.url("create"),
            {
                "name": "Bad",
                "customer_name": "C",
                "status": ProjectStatus.READY,
                "manager": self.pm.pk,
                "planned_start_date": today,
                "planned_end_date": today - timedelta(days=1),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Project.objects.filter(name="Bad").exists())

    def test_pm_adds_and_removes_member(self):
        self.login(self.pm)
        self.client.post(self.url("member_add", self.project.pk), {"user": self.other.pk, "project_role": "QA"})
        membership = ProjectMember.objects.get(project=self.project, user=self.other)
        self.client.post(self.url("member_remove", self.project.pk, membership.pk))
        self.assertFalse(ProjectMember.objects.filter(pk=membership.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.DELETE, object_id=str(membership.pk)).exists())


class TaskTests(ProjectTestCase):
    def setUp(self):
        self.task = ProjectTask.objects.create(project=self.project, title="Survey", assignee=self.member)
        self.pm_task = ProjectTask.objects.create(project=self.project, title="Plan", assignee=self.pm)

    def test_task_assignee_must_be_project_participant(self):
        self.login(self.pm)
        response = self.client.post(self.url("task_create", self.project.pk), {"title": "X", "assignee": self.other.pk, "priority": "MEDIUM"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ProjectTask.objects.filter(title="X").exists())

    def test_member_updates_own_task_status_and_history_is_kept(self):
        self.login(self.member)
        url = self.url("task_status", self.project.pk, self.task.pk)
        self.client.post(url, {"status": TaskStatus.IN_PROGRESS, "percent": 30, "note": "Started"})
        self.client.post(url, {"status": TaskStatus.DONE, "percent": 100, "note": ""})

        self.task.refresh_from_db()
        self.assertEqual(self.task.status, TaskStatus.DONE)
        self.assertIsNotNone(self.task.completed_at)
        updates = list(ProgressUpdate.objects.filter(task=self.task).order_by("created_at", "id"))
        self.assertEqual([(u.status_from, u.status_to) for u in updates], [("TODO", "IN_PROGRESS"), ("IN_PROGRESS", "DONE")])
        self.assertTrue(all(u.author == self.member for u in updates))
        self.assertEqual(AuditLog.objects.filter(object_id=str(self.task.pk), action=AuditLog.Action.UPDATE).count(), 2)

    def test_member_cannot_update_someone_elses_task(self):
        self.login(self.member)
        response = self.client.post(self.url("task_status", self.project.pk, self.pm_task.pk), {"status": TaskStatus.DONE})
        self.assertEqual(response.status_code, 403)
        self.pm_task.refresh_from_db()
        self.assertEqual(self.pm_task.status, TaskStatus.TODO)

    def test_member_cannot_touch_tasks_of_invisible_project(self):
        hidden_task = ProjectTask.objects.create(project=self.hidden, title="Secret", assignee=self.other)
        self.login(self.member)
        response = self.client.post(self.url("task_status", self.hidden.pk, hidden_task.pk), {"status": TaskStatus.DONE})
        self.assertEqual(response.status_code, 404)

    def test_member_progress_update_limited_to_own_tasks(self):
        self.login(self.member)
        response = self.client.post(
            self.url("progress_create", self.project.pk), {"task": self.pm_task.pk, "percent": 10, "note": "x"}
        )
        self.assertEqual(response.status_code, 200)  # invalid choice re-renders form
        self.client.post(self.url("progress_create", self.project.pk), {"task": self.task.pk, "percent": 10, "note": "ok"})
        self.assertTrue(ProgressUpdate.objects.filter(task=self.task, author=self.member, percent=10).exists())


class IssueTests(ProjectTestCase):
    def test_member_reports_issue_and_only_involved_users_can_edit(self):
        self.login(self.member)
        self.client.post(
            self.url("issue_create", self.project.pk),
            {"kind": "ISSUE", "title": "Late supplier", "severity": "HIGH", "status": "OPEN"},
        )
        issue = ProjectIssue.objects.get(title="Late supplier")
        self.assertEqual(issue.reported_by, self.member)

        outsider = make_user("outsider", roles.PROJECT_MEMBER)
        ProjectMember.objects.create(project=self.project, user=outsider)
        self.login(outsider)
        self.assertEqual(self.client.get(self.url("issue_update", self.project.pk, issue.pk)).status_code, 403)

    def test_resolving_sets_resolved_at(self):
        issue = ProjectIssue.objects.create(project=self.project, title="I", reported_by=self.member)
        self.assertIsNone(issue.resolved_at)
        issue.status = "RESOLVED"
        issue.save()
        self.assertIsNotNone(issue.resolved_at)


class FinanceVisibilityTests(ProjectTestCase):
    def setUp(self):
        ProjectContract.objects.create(project=self.project, title="HĐ", contract_value=Decimal("987654321"))

    def test_member_does_not_see_contract_value(self):
        self.login(self.member)
        response = self.client.get(self.url("detail", self.project.pk))
        self.assertNotContains(response, "987.654.321")

    def test_finance_viewer_member_sees_contract_value(self):
        viewer = make_user("fin", roles.PROJECT_MEMBER, roles.FINANCE_VIEWER)
        ProjectMember.objects.create(project=self.project, user=viewer)
        self.login(viewer)
        self.assertContains(self.client.get(self.url("detail", self.project.pk)), "987.654.321")


class HandoverTests(ProjectTestCase):
    def setUp(self):
        self.handover = SalesHandover.objects.create(
            customer_name="Cust H", deal_name="Deal H", external_opportunity_id="OPP-1", committed_value=Decimal("100")
        )

    def test_duplicate_opportunity_is_rejected_by_form(self):
        self.login(self.pm)
        response = self.client.post(
            reverse("projects:handover_create"),
            {"deal_name": "Again", "customer_name": "Cust H", "external_opportunity_id": "OPP-1", "currency": "VND"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SalesHandover.objects.filter(external_opportunity_id="OPP-1").count(), 1)

    def test_cannot_create_project_from_pending_handover(self):
        project = Project(name="P", customer_name="C", manager=self.pm)
        with self.assertRaises(ValidationError):
            services.create_project_from_handover(self.handover, self.pm, project)

    def test_accepted_handover_creates_exactly_one_project(self):
        services.review_handover(self.handover, self.pm, HandoverStatus.ACCEPTED, "OK")
        self.login(self.pm)
        data = {"name": "From handover", "customer_name": "Cust H", "status": ProjectStatus.READY, "manager": self.pm.pk}
        url = reverse("projects:handover_create_project", args=[self.handover.pk])
        self.client.post(url, data)
        self.client.post(url, data)  # double submit
        self.assertEqual(Project.objects.filter(handover=self.handover).count(), 1)

        # Once a project exists the handover is locked.
        with self.assertRaises(ValidationError):
            services.review_handover(self.handover, self.pm, HandoverStatus.REJECTED, "no")

    def test_review_requires_note_when_rejecting(self):
        self.login(self.pm)
        self.client.post(reverse("projects:handover_review", args=[self.handover.pk]), {"status": "REJECTED", "review_note": ""})
        self.handover.refresh_from_db()
        self.assertEqual(self.handover.status, HandoverStatus.PENDING)

    def test_handover_access_by_role(self):
        sales = make_user("sales", roles.SALES_VIEWER)
        self.login(sales)
        response = self.client.get(reverse("projects:handover_detail", args=[self.handover.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("projects:handover_create")).status_code, 403)
        self.login(self.member)
        self.assertEqual(self.client.get(reverse("projects:handover_list")).status_code, 403)
