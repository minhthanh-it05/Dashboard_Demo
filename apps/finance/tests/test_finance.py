from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts import roles
from apps.core.models import SourceSystem
from apps.core.testing import TEST_PASSWORD, make_user
from apps.finance import csv_import
from apps.finance.models import FinanceDataKind, FinanceImportBatch, ImportStatus
from apps.finance.sync import run_misa_sync
from apps.integrations.models import SyncStatus

AS_OF = date(2026, 10, 31)
DEBT = FinanceDataKind.DEBT_BALANCE
HEADER = "counterparty_code,counterparty_name,receivable_amount,payable_amount,currency\n"


def debt_csv(*rows):
    return (HEADER + "".join(f"{r}\n" for r in rows)).encode("utf-8")


def import_debt(raw):
    return csv_import.import_file(raw, filename="debt.csv", data_kind=DEBT, as_of_date=AS_OF, user=None)


class CsvImportTests(TestCase):
    def test_valid_file_becomes_current_snapshot(self):
        batch = import_debt(debt_csv("KH1,Khách 1,1500.50,0,VND", "NCC1,NCC 1,,200,"))
        self.assertEqual(batch.status, ImportStatus.IMPORTED)
        self.assertTrue(batch.is_current)
        self.assertEqual(batch.source_system, SourceSystem.FINANCE_CSV)
        rows = list(batch.debt_rows.all())
        self.assertEqual(rows[0].receivable_amount, Decimal("1500.50"))
        self.assertIsNone(rows[1].receivable_amount)
        self.assertEqual(rows[1].currency, "VND")

    def test_utf8_bom_is_accepted(self):
        batch = import_debt(b"\xef\xbb\xbf" + debt_csv("KH1,Khách 1,1,0,VND"))
        self.assertEqual(batch.status, ImportStatus.IMPORTED)

    def test_any_bad_row_rejects_whole_file(self):
        batch = import_debt(debt_csv("KH1,Khách 1,100,0,VND", "KH2,,1.000.000,0,VND"))
        self.assertEqual(batch.status, ImportStatus.REJECTED)
        self.assertEqual(batch.debt_rows.count(), 0)
        self.assertTrue(any("Dòng 3" in e for e in batch.errors))
        self.assertEqual(len(batch.errors), 1)  # first failing check on that row

    def test_missing_columns(self):
        batch = import_debt(b"code,name\nKH1,A\n")
        self.assertEqual(batch.status, ImportStatus.REJECTED)
        self.assertIn("Thiếu cột", batch.errors[0])

    def test_duplicate_keys_rejected(self):
        batch = import_debt(debt_csv("KH1,A,1,0,VND", "KH1,A again,2,0,VND"))
        self.assertEqual(batch.status, ImportStatus.REJECTED)
        self.assertIn("KH1", batch.errors[0])

    def test_same_file_twice_is_rejected(self):
        raw = debt_csv("KH1,A,1,0,VND")
        import_debt(raw)
        second = import_debt(raw)
        self.assertEqual(second.status, ImportStatus.REJECTED)
        self.assertEqual(FinanceImportBatch.objects.filter(status=ImportStatus.IMPORTED).count(), 1)

    def test_new_import_supersedes_previous(self):
        first = import_debt(debt_csv("KH1,A,1,0,VND"))
        second = import_debt(debt_csv("KH1,A,2,0,VND"))
        first.refresh_from_db()
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)

    def test_non_utf8(self):
        batch = import_debt(HEADER.encode() + "KH1,Khách,1,0,VND\n".encode("cp1258"))
        self.assertEqual(batch.status, ImportStatus.REJECTED)


class MisaSyncTests(TestCase):
    def test_mock_sync_creates_simulated_current_snapshots_and_is_rerunnable(self):
        runs = run_misa_sync()
        self.assertTrue(all(r.status == SyncStatus.SUCCESS and r.is_simulated for r in runs))
        run_misa_sync()

        current = FinanceImportBatch.objects.filter(is_current=True)
        self.assertEqual(current.count(), 2)
        self.assertTrue(all(b.is_simulated and b.source_system == SourceSystem.MISA_ACT_API for b in current))
        debt = current.get(data_kind=DEBT)
        self.assertEqual(debt.debt_rows.count(), 5)
        self.assertIsNotNone(debt.sync_run)

    @override_settings(MISA_MODE="live", MISA_APP_ID="")
    def test_live_mode_not_ready(self):
        from apps.integrations.exceptions import IntegrationNotReady

        with self.assertRaises(IntegrationNotReady):
            run_misa_sync()


class FinanceViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = make_user("member", roles.PROJECT_MEMBER)
        cls.pm = make_user("pm", roles.PROJECT_MANAGER)
        cls.finance = make_user("fin", roles.FINANCE_VIEWER)

    def login(self, user):
        self.client.login(username=user.username, password=TEST_PASSWORD)

    def test_access_rules(self):
        self.login(self.member)
        self.assertEqual(self.client.get(reverse("finance:overview")).status_code, 403)
        self.login(self.pm)
        self.assertEqual(self.client.get(reverse("finance:overview")).status_code, 200)
        self.assertEqual(self.client.get(reverse("finance:import")).status_code, 403)

    def test_importers_can_always_see_finance(self):
        users = [self.member, self.pm, self.finance, make_user("sysadmin", roles.SYSTEM_ADMIN)]
        for user in users:
            with self.subTest(user=user.username):
                if roles.can_import_finance(user):
                    self.assertTrue(roles.can_view_finance(user))

    def test_upload_flow(self):
        self.login(self.finance)
        upload = SimpleUploadedFile("debt.csv", debt_csv("KH1,Khách 1,1234567,0,VND"), content_type="text/csv")
        response = self.client.post(
            reverse("finance:import"), {"data_kind": DEBT, "as_of_date": "2026-10-31", "file": upload}
        )
        batch = FinanceImportBatch.objects.get()
        self.assertRedirects(response, reverse("finance:batch_detail", args=[batch.pk]))
        self.assertEqual(batch.imported_by, self.finance)
        self.assertContains(self.client.get(reverse("finance:overview")), "1.234.567")

    def test_upload_rejects_non_csv_extension(self):
        self.login(self.finance)
        upload = SimpleUploadedFile("debt.xlsx", b"x")
        response = self.client.post(reverse("finance:import"), {"data_kind": DEBT, "as_of_date": "2026-10-31", "file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FinanceImportBatch.objects.exists())
