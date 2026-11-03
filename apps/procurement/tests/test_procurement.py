from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts import roles
from apps.core.models import StatusSource
from apps.core.testing import TEST_PASSWORD, make_user
from apps.payments.models import PaymentRequest
from apps.procurement.models import PurchaseItem, PurchaseRequest, PurchaseStatusEntry
from apps.projects.models import Project, ProjectMember


class TrackingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pm = make_user("pm", roles.PROJECT_MANAGER)
        cls.member = make_user("member", roles.PROJECT_MEMBER)
        cls.project = Project.objects.create(name="Alpha", customer_name="C", manager=cls.pm)
        ProjectMember.objects.create(project=cls.project, user=cls.member)
        cls.pr = PurchaseRequest.objects.create(project=cls.project, title="Cameras", requester=cls.pm)
        PurchaseItem.objects.create(purchase_request=cls.pr, description="Cam", quantity=2, unit_cost=Decimal("1234567"))

    def login(self, user):
        self.client.login(username=user.username, password=TEST_PASSWORD)

    def test_request_numbers_are_generated(self):
        self.assertTrue(self.pr.request_number.startswith("PR-"))
        pay = PaymentRequest.objects.create(project=self.project, payee_name="X", reason="r", requester=self.pm)
        self.assertTrue(pay.request_number.startswith("PAY-"))

    def test_estimated_total(self):
        self.assertEqual(self.pr.estimated_total, Decimal("2469134"))

    def test_misa_referenced_status_requires_evidence(self):
        self.login(self.pm)
        url = reverse("procurement:status_create", args=[self.project.pk, self.pr.pk])
        self.client.post(url, {"status_label": "Đã duyệt trên MISA", "status_source": StatusSource.MISA_REFERENCED})
        self.assertFalse(PurchaseStatusEntry.objects.exists())
        self.client.post(
            url,
            {
                "status_label": "Đã duyệt trên MISA",
                "status_source": StatusSource.MISA_REFERENCED,
                "evidence_note": "Chứng từ MISA số 123, kế toán X xác nhận",
            },
        )
        entry = PurchaseStatusEntry.objects.get()
        self.assertEqual(entry.recorded_by, self.pm)

    def test_demo_source_cannot_be_chosen_by_users(self):
        self.login(self.pm)
        url = reverse("procurement:status_create", args=[self.project.pk, self.pr.pk])
        self.client.post(url, {"status_label": "x", "status_source": StatusSource.DEMO})
        self.assertFalse(PurchaseStatusEntry.objects.exists())

    def test_member_can_view_but_not_change_and_sees_no_amounts(self):
        self.login(self.member)
        detail = self.client.get(self.pr.get_absolute_url())
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, "1.234.567")
        self.assertEqual(self.client.get(reverse("procurement:create", args=[self.project.pk])).status_code, 403)
        url = reverse("procurement:status_create", args=[self.project.pk, self.pr.pk])
        self.assertEqual(self.client.post(url, {"status_label": "x", "status_source": "INTERNAL"}).status_code, 403)

    def test_pm_sees_amounts(self):
        self.login(self.pm)
        self.assertContains(self.client.get(self.pr.get_absolute_url()), "1.234.567")

    def test_payment_amount_dropped_from_form_for_non_finance(self):
        from apps.payments.forms import PaymentRequestForm

        form = PaymentRequestForm(project=self.project, user=self.member)
        self.assertNotIn("amount", form.fields)
        form = PaymentRequestForm(project=self.project, user=self.pm)
        self.assertIn("amount", form.fields)

    def test_pm_creates_payment_request_linked_to_purchase(self):
        self.login(self.pm)
        response = self.client.post(
            reverse("payments:create", args=[self.project.pk]),
            {
                "payee_name": "NCC A",
                "amount": "5000000",
                "currency": "VND",
                "reason": "Tạm ứng",
                "purchase_request": self.pr.pk,
                "request_date": "2026-11-01",
            },
        )
        payment = PaymentRequest.objects.get(payee_name="NCC A")
        self.assertRedirects(response, payment.get_absolute_url())
        self.assertEqual(payment.requester, self.pm)
        self.assertEqual(payment.purchase_request, self.pr)
