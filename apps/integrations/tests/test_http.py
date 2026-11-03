from unittest import mock

import requests
from django.test import SimpleTestCase

from apps.integrations.exceptions import RemoteApiError, ResponseFormatError, TransientError
from apps.integrations.http import JsonHttpClient, RetryPolicy


def response(status=200, payload=None, headers=None):
    resp = mock.Mock(status_code=status, headers=headers or {})
    if isinstance(payload, Exception):
        resp.json.side_effect = payload
    else:
        resp.json.return_value = payload
    return resp


class JsonHttpClientTests(SimpleTestCase):
    def make_client(self, *responses):
        session = mock.Mock()
        session.request.side_effect = list(responses)
        sleeps = []
        client = JsonHttpClient(
            "https://example.test/", retry=RetryPolicy(max_attempts=3, backoff_seconds=1), session=session, sleep=sleeps.append
        )
        return client, session, sleeps

    def test_returns_json_and_builds_url(self):
        client, session, _ = self.make_client(response(payload={"ok": True}))
        self.assertEqual(client.post("/a/b", json={"x": 1}), {"ok": True})
        _, url = session.request.call_args.args
        self.assertEqual(url, "https://example.test/a/b")
        self.assertEqual(session.request.call_args.kwargs["timeout"], 30)

    def test_retries_transient_errors_with_backoff(self):
        client, session, sleeps = self.make_client(
            requests.Timeout(), response(503), response(payload={"ok": True})
        )
        self.assertEqual(client.post("/x"), {"ok": True})
        self.assertEqual(session.request.call_count, 3)
        self.assertEqual(sleeps, [1, 2])

    def test_honours_retry_after(self):
        client, _, sleeps = self.make_client(response(429, headers={"Retry-After": "7"}), response(payload={}))
        client.post("/x")
        self.assertEqual(sleeps, [7.0])

    def test_gives_up_after_max_attempts(self):
        client, session, _ = self.make_client(response(500), response(500), response(500))
        with self.assertRaises(TransientError):
            client.post("/x")
        self.assertEqual(session.request.call_count, 3)

    def test_client_errors_are_not_retried(self):
        client, session, _ = self.make_client(response(401))
        with self.assertRaises(RemoteApiError):
            client.post("/x")
        self.assertEqual(session.request.call_count, 1)

    def test_non_json_body(self):
        client, _, _ = self.make_client(response(payload=ValueError("bad")))
        with self.assertRaises(ResponseFormatError):
            client.post("/x")

    def test_throttle_waits_between_requests(self):
        session = mock.Mock()
        session.request.side_effect = [response(payload={}), response(payload={})]
        sleeps = []
        ticks = iter([0.0, 0.2, 1.0])  # 1st send; 2nd send 0.2s later; after sleeping
        client = JsonHttpClient(
            "https://example.test", session=session, sleep=sleeps.append, clock=lambda: next(ticks), min_interval_seconds=1.0
        )
        client.post("/a")
        client.post("/b")
        self.assertEqual(len(sleeps), 1)
        self.assertAlmostEqual(sleeps[0], 0.8)
