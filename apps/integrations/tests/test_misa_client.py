import json
from datetime import datetime, timedelta, timezone as dt_timezone

from django.test import SimpleTestCase

from apps.integrations.exceptions import RemoteApiError, ResponseFormatError, WriteNotAllowed
from apps.integrations.misa.act_client import CONNECT_PATH, TOKEN_HEADER, MisaActClient, parse_envelope

NOW = datetime(2026, 11, 3, 8, 0, tzinfo=dt_timezone.utc)


def ok(data, custom=None):
    return {"Success": True, "ErrorCode": None, "ErrorMessage": None, "Data": data, "CustomData": custom}


class FakeHttp:
    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = []

    def post(self, path, *, json=None, headers=None):
        self.calls.append((path, json, headers))
        if path == CONNECT_PATH:
            return ok({"access_token": f"token-{len(self.calls)}", "expired_time": "2026-11-03T20:00:00+00:00"})
        return self.pages.pop(0)


class EnvelopeTests(SimpleTestCase):
    def test_data_encoded_as_json_string_is_decoded(self):
        envelope = parse_envelope(ok(json.dumps([{"a": 1}]), {"LastSyncTime": "x"}))
        self.assertEqual(envelope.data, [{"a": 1}])
        self.assertEqual(envelope.custom_data, {"LastSyncTime": "x"})

    def test_failure_raises_remote_error(self):
        with self.assertRaises(RemoteApiError):
            parse_envelope({"Success": False, "ErrorCode": "E1", "ErrorMessage": "nope"})

    def test_malformed_payloads(self):
        for payload in ([], {"Data": []}, ok("{not json")):
            with self.subTest(payload=payload), self.assertRaises(ResponseFormatError):
                parse_envelope(payload)


class MisaActClientTests(SimpleTestCase):
    def make_client(self, pages, now=lambda: NOW):
        http = FakeHttp(pages)
        client = MisaActClient(http, app_id="app", access_code="code", org_company_code="org", now=now)
        return client, http

    def test_write_actions_are_refused_without_network(self):
        client, http = self.make_client([])
        for action in ("save", "delete", "set_option", "save_dictionary"):
            with self.subTest(action=action), self.assertRaises(WriteNotAllowed):
                client.read(action)
        self.assertEqual(http.calls, [])

    def test_token_is_sent_and_reused_until_near_expiry(self):
        clock = {"now": NOW}
        client, http = self.make_client([ok([]), ok([]), ok([])], now=lambda: clock["now"])
        client.read("get_company_info")
        client.read("get_company_info")
        connects = [c for c in http.calls if c[0] == CONNECT_PATH]
        self.assertEqual(len(connects), 1)
        self.assertEqual(http.calls[1][2], {TOKEN_HEADER: "token-1"})

        clock["now"] = NOW + timedelta(hours=11, minutes=55)  # inside refresh margin
        client.read("get_company_info")
        self.assertEqual(len([c for c in http.calls if c[0] == CONNECT_PATH]), 2)

    def test_iter_rows_paginates_with_skip_take(self):
        full_page = [{"i": n} for n in range(100)]
        client, http = self.make_client([ok(full_page), ok(json.dumps([{"i": 100}]))])
        rows = list(client.iter_rows("get_list_acc_obj_debt"))
        self.assertEqual(len(rows), 101)
        bodies = [c[1] for c in http.calls if c[0] != CONNECT_PATH]
        self.assertEqual([(b["skip"], b["take"]) for b in bodies], [(0, 100), (100, 100)])

    def test_iter_rows_rejects_non_list_data(self):
        client, _ = self.make_client([ok({"not": "a list"})])
        with self.assertRaises(ResponseFormatError):
            list(client.iter_rows("get_list_acc_obj_debt"))
