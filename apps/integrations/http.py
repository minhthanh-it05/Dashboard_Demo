"""Vendor-neutral JSON-over-HTTP client with timeouts and bounded retries.

Logs only the method, path and error class — never headers, bodies or
tokens (CLAUDE.md §8.7).
"""

import logging
import time
from dataclasses import dataclass

import requests

from .exceptions import RemoteApiError, ResponseFormatError, TransientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 1.0
    retry_statuses: frozenset = frozenset({429, 500, 502, 503, 504})


class JsonHttpClient:
    def __init__(
        self,
        base_url,
        *,
        timeout_seconds=30,
        retry=RetryPolicy(),
        min_interval_seconds=0.0,
        session=None,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.retry = retry
        self.min_interval_seconds = min_interval_seconds
        self.session = session or requests.Session()
        self._sleep = sleep
        self._clock = clock
        self._last_request_at = None

    def post(self, path, *, json=None, headers=None):
        return self.request("POST", path, json=json, headers=headers)

    def request(self, method, path, *, json=None, headers=None):
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(1, self.retry.max_attempts + 1):
            try:
                return self._send_once(method, url, path, json, headers)
            except TransientError as exc:
                if attempt == self.retry.max_attempts:
                    raise
                delay = exc.retry_after or self.retry.backoff_seconds * 2 ** (attempt - 1)
                logger.warning("Retrying %s %s in %.1fs (attempt %d): %s", method, path, delay, attempt, exc)
                self._sleep(delay)

    def _send_once(self, method, url, path, json, headers):
        self._throttle()
        try:
            response = self.session.request(method, url, json=json, headers=headers, timeout=self.timeout_seconds)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise TransientError(f"{method} {path}: {exc.__class__.__name__}") from exc

        if response.status_code in self.retry.retry_statuses:
            raise TransientError(f"{method} {path}: HTTP {response.status_code}", _retry_after(response))
        if response.status_code >= 400:
            raise RemoteApiError(f"{method} {path}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ResponseFormatError(f"{method} {path}: response is not JSON") from exc

    def _throttle(self):
        """Keep a minimum gap between requests; vendors' rate limits are unknown."""
        if self._last_request_at is not None and self.min_interval_seconds:
            wait = self.min_interval_seconds - (self._clock() - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = self._clock()


def _retry_after(response):
    value = response.headers.get("Retry-After", "")
    return float(value) if value.isdigit() else None
