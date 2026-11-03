from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.templatetags.ui import money
from apps.core.testing import make_user


class HealthCheckTests(TestCase):
    def test_health_is_public_and_reports_db(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


class AuditHelperTests(TestCase):
    def test_diff_reports_only_changed_fields(self):
        before = {"status": "TODO", "title": "A"}
        after = {"status": "DONE", "title": "A"}
        self.assertEqual(audit.diff(before, after), {"status": {"old": "TODO", "new": "DONE"}})

    def test_record_stores_actor_and_object(self):
        user = make_user("auditor")
        log = audit.record(user, user, AuditLog.Action.UPDATE, {"x": {"old": 1, "new": 2}})
        self.assertEqual(log.actor, user)
        self.assertEqual(log.object_id, str(user.pk))


class MoneyFilterTests(TestCase):
    def test_vnd_has_no_decimals(self):
        self.assertEqual(money(Decimal("1250000"), "VND"), "1.250.000 VND")

    def test_none_is_dash(self):
        self.assertEqual(money(None, "VND"), "—")
