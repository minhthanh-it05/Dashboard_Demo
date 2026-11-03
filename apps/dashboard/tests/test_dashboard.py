from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.core.testing import TEST_PASSWORD, make_user
from apps.projects.models import Project, ProjectMember, ProjectTask, SalesHandover, TaskStatus


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pm = make_user("pm", roles.PROJECT_MANAGER)
        cls.member = make_user("member", roles.PROJECT_MEMBER)
        cls.other = make_user("other", roles.PROJECT_MEMBER)
        yesterday = timezone.localdate() - timedelta(days=1)
        cls.project = Project.objects.create(name="Alpha", customer_name="C", manager=cls.pm)
        cls.hidden = Project.objects.create(name="Beta", customer_name="C", manager=cls.pm)
        ProjectMember.objects.create(project=cls.project, user=cls.member)
        ProjectTask.objects.create(project=cls.project, title="Mine overdue", assignee=cls.member, due_date=yesterday)
        ProjectTask.objects.create(project=cls.project, title="Done", assignee=cls.member, status=TaskStatus.DONE)
        ProjectTask.objects.create(project=cls.hidden, title="Not mine", assignee=cls.other, due_date=yesterday)

    def login(self, user):
        self.client.login(username=user.username, password=TEST_PASSWORD)

    def test_home_redirects_by_role(self):
        self.login(self.pm)
        self.assertRedirects(self.client.get(reverse("dashboard:home")), reverse("dashboard:pm"))
        self.login(self.member)
        self.assertRedirects(self.client.get(reverse("dashboard:home")), reverse("dashboard:my_work"))

    def test_pm_dashboard(self):
        self.login(self.pm)
        response = self.client.get(reverse("dashboard:pm"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_projects"], 2)
        self.assertEqual({t.title for t in response.context["overdue_tasks"]}, {"Mine overdue", "Not mine"})
        self.assertEqual(set(response.context["at_risk_projects"]), {self.project, self.hidden})

    def test_member_cannot_open_pm_dashboard(self):
        self.login(self.member)
        self.assertEqual(self.client.get(reverse("dashboard:pm")).status_code, 403)

    def test_my_work_shows_only_my_open_tasks(self):
        self.login(self.member)
        response = self.client.get(reverse("dashboard:my_work"))
        self.assertEqual([t.title for t in response.context["my_tasks"]], ["Mine overdue"])
        self.assertEqual(len(response.context["overdue_tasks"]), 1)
        self.assertNotContains(response, "Not mine")


class SeedCommandTests(TestCase):
    @override_settings(DEBUG=True)
    def test_seed_is_idempotent_and_flags_demo_data(self):
        call_command("seed_demo_data", password="Demo-pass-123", stdout=StringIO())
        call_command("seed_demo_data", password="Demo-pass-123", stdout=StringIO())
        self.assertEqual(Project.objects.count(), 3)
        self.assertFalse(Project.objects.filter(is_demo_data=False).exists())
        self.assertFalse(SalesHandover.objects.filter(is_demo_data=False).exists())

        call_command("seed_demo_data", password="Demo-pass-123", reset=True, stdout=StringIO())
        self.assertEqual(Project.objects.count(), 3)

    def test_seed_refuses_without_debug(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo_data", password="x", stdout=StringIO())
