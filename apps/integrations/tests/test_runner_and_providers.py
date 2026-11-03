from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.integrations.exceptions import IntegrationDisabled, IntegrationNotReady, RemoteApiError
from apps.integrations.misa import live as misa_live
from apps.integrations.misa.provider import get_provider as get_misa_provider
from apps.integrations.models import ExternalSystem, SyncMode, SyncState, SyncStatus
from apps.integrations.oplacrm.mock import MockOplaCRMProvider
from apps.integrations.oplacrm.provider import get_provider as get_oplacrm_provider
from apps.integrations.runner import CREATED, UNCHANGED, UPDATED, run_sync, upsert


def run(sync_fn):
    return run_sync(ExternalSystem.OPLACRM, "test", SyncMode.MOCK, sync_fn)


class RunSyncTests(TestCase):
    def test_success_advances_cursor(self):
        result = run(lambda ctx: "cursor-1")
        self.assertEqual(result.status, SyncStatus.SUCCESS)
        state = SyncState.objects.get(system=ExternalSystem.OPLACRM, entity="test")
        self.assertEqual(state.cursor, "cursor-1")
        self.assertEqual(state.last_run, result)

    def test_partial_does_not_advance_cursor(self):
        run(lambda ctx: "cursor-1")

        def partly_failing(ctx):
            ctx.stats.record_error("rec-9", "bad record")
            return "cursor-2"

        result = run(partly_failing)
        self.assertEqual(result.status, SyncStatus.PARTIAL)
        self.assertEqual(result.errors, [{"ref": "rec-9", "message": "bad record"}])
        self.assertEqual(SyncState.objects.get(entity="test").cursor, "cursor-1")

    def test_integration_error_is_recorded_as_failed(self):
        def failing(ctx):
            raise RemoteApiError("HTTP 401")

        result = run(failing)
        self.assertEqual(result.status, SyncStatus.FAILED)
        self.assertEqual(result.message, "HTTP 401")

    def test_unexpected_error_hides_details(self):
        def crashing(ctx):
            raise KeyError("secret-token-value")

        with self.assertLogs("apps.integrations.runner", level="ERROR"):
            result = run(crashing)
        self.assertEqual(result.status, SyncStatus.FAILED)
        self.assertNotIn("secret", result.message)


class UpsertTests(TestCase):
    def test_outcomes_ignore_touch_fields(self):
        lookup = {"system": ExternalSystem.OPLACRM, "entity": "x"}

        def save(cursor):
            return upsert(SyncState, lookup=lookup, values={"cursor": cursor}, touch={"last_success_at": timezone.now()})

        self.assertEqual(save("a")[1], CREATED)
        self.assertEqual(save("a")[1], UNCHANGED)
        self.assertEqual(save("b")[1], UPDATED)
        self.assertEqual(SyncState.objects.get().cursor, "b")


class ProviderFactoryTests(SimpleTestCase):
    @override_settings(OPLACRM_MODE="mock")
    def test_mock_mode(self):
        self.assertIsInstance(get_oplacrm_provider(), MockOplaCRMProvider)

    @override_settings(OPLACRM_MODE="disabled")
    def test_disabled_mode(self):
        with self.assertRaises(IntegrationDisabled):
            get_oplacrm_provider()

    @override_settings(OPLACRM_MODE="bogus")
    def test_unknown_mode(self):
        with self.assertRaises(ImproperlyConfigured):
            get_oplacrm_provider()

    @override_settings(OPLACRM_MODE="live", OPLACRM_BASE_URL="https://crm.example.test")
    def test_oplacrm_live_is_not_ready(self):
        provider = get_oplacrm_provider()
        with self.assertRaises(IntegrationNotReady):
            list(provider.iter_accounts(None))

    @override_settings(MISA_MODE="live", MISA_APP_ID="")
    def test_misa_live_requires_credentials(self):
        with self.assertRaises(IntegrationNotReady):
            get_misa_provider()

    @override_settings(
        MISA_MODE="live",
        MISA_ACT_BASE_URL="https://misa.example.test",
        MISA_APP_ID="a",
        MISA_ACCESS_CODE="b",
        MISA_ORG_COMPANY_CODE="c",
    )
    def test_misa_live_refuses_before_any_network_call(self):
        provider = get_misa_provider()
        with mock.patch.object(misa_live.MisaActClient, "iter_rows") as iter_rows:
            with self.assertRaises(IntegrationNotReady):
                provider.fetch_debt_balances()
            iter_rows.assert_not_called()

    def test_mock_provider_filters_by_updated_since(self):
        provider = MockOplaCRMProvider()
        everything = list(provider.iter_accounts(None))
        newest = max(record.updated_at for record in everything)
        self.assertEqual(list(provider.iter_accounts(newest)), [])
