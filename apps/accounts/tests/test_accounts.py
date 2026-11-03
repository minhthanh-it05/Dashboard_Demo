from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from apps.accounts import roles
from apps.core.testing import TEST_PASSWORD, make_user


class RoleGroupsTests(TestCase):
    def test_role_groups_exist_after_migrate(self):
        names = set(Group.objects.values_list("name", flat=True))
        self.assertTrue(set(roles.ALL_ROLES) <= names)


class RoleCheckTests(TestCase):
    def test_role_checks(self):
        pm = make_user("pm", roles.PROJECT_MANAGER)
        member = make_user("member", roles.PROJECT_MEMBER)
        finance = make_user("fin", roles.FINANCE_VIEWER)
        sales = make_user("sales", roles.SALES_VIEWER)

        self.assertTrue(roles.is_project_manager(pm))
        self.assertFalse(roles.is_project_manager(member))
        self.assertTrue(roles.can_view_finance(pm))
        self.assertTrue(roles.can_view_finance(finance))
        self.assertFalse(roles.can_view_finance(member))
        self.assertFalse(roles.can_view_finance(sales))
        self.assertTrue(roles.can_view_handovers(sales))
        self.assertFalse(roles.can_view_handovers(member))


class LoginTests(TestCase):
    def test_pages_require_login(self):
        response = self.client.get(reverse("projects:list"))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('projects:list')}")

    def test_login_and_logout(self):
        make_user("member", roles.PROJECT_MEMBER)
        response = self.client.post(reverse("accounts:login"), {"username": "member", "password": TEST_PASSWORD})
        self.assertRedirects(response, reverse("dashboard:home"), fetch_redirect_response=False)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("accounts:login"))
