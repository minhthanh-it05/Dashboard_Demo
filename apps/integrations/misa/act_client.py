"""Client for the MISA AMIS ACT Open API.

UNVERIFIED: written from the team's notes (CLAUDE.md §5.2), not from vendor
documentation or a real tenant. Every detail marked "per notes" must be
checked with MISA before live use (docs/OPEN_QUESTIONS.md, section E).

Read-only by construction: only actions in READ_ACTIONS can be called.
"""

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.integrations.exceptions import RemoteApiError, ResponseFormatError, WriteNotAllowed

CONNECT_PATH = "/api/oauth/actopen/connect"  # per notes
ACTION_PATH = "/apir/sync/actopen/{action}"  # per notes
TOKEN_HEADER = "X-MISA-AccessToken"  # per notes

READ_ACTIONS = frozenset(
    {
        "get_dictionary",
        "get_dictionary_delete",
        "get_list_acc_obj_debt",
        "get_list_acc_obj_debt_delete",
        "get_list_inventory_balance",
        "get_list_inventory_balance_delete",
        "get_company_info",
        "get_option",
    }
)

MAX_TAKE = 100  # per notes
DEFAULT_TOKEN_LIFETIME = timedelta(hours=12)  # per notes; used only if expiry is missing
TOKEN_REFRESH_MARGIN = timedelta(minutes=10)


@dataclass(frozen=True)
class ActEnvelope:
    data: Any
    custom_data: Any


def parse_envelope(payload):
    """Parse the common response {Success, ErrorCode, ErrorMessage, Data, CustomData}.

    `Data` may itself be a JSON-encoded string (per notes), so it is decoded
    a second time when needed.
    """
    if not isinstance(payload, dict) or "Success" not in payload:
        raise ResponseFormatError("MISA: response is not the expected envelope")
    if not payload["Success"]:
        raise RemoteApiError(f"MISA ErrorCode={payload.get('ErrorCode')}: {payload.get('ErrorMessage') or 'no message'}")

    data = payload.get("Data")
    if isinstance(data, str) and data:
        try:
            data = json.loads(data)
        except ValueError as exc:
            raise ResponseFormatError("MISA: Data is a string but not valid JSON") from exc
    return ActEnvelope(data=data, custom_data=payload.get("CustomData"))


class MisaActClient:
    def __init__(self, http, *, app_id, access_code, org_company_code, now=timezone.now):
        self._http = http
        self._credentials = {"app_id": app_id, "access_code": access_code, "org_company_code": org_company_code}
        self._now = now
        self._token = None
        self._token_expires_at = None

    def read(self, action, body=None):
        if action not in READ_ACTIONS:
            raise WriteNotAllowed(f"MISA action '{action}' is not an approved read action.")
        payload = self._http.post(
            ACTION_PATH.format(action=action),
            json=body or {},
            headers={TOKEN_HEADER: self._access_token()},
        )
        return parse_envelope(payload)

    def iter_rows(self, action, body=None, take=MAX_TAKE):
        """Yield rows across pages using skip/take (per notes)."""
        take = min(take, MAX_TAKE)
        skip = 0
        while True:
            rows = self.read(action, {**(body or {}), "skip": skip, "take": take}).data or []
            if not isinstance(rows, list):
                raise ResponseFormatError(f"MISA {action}: expected a list of rows")
            yield from rows
            if len(rows) < take:
                return
            skip += take

    def _access_token(self):
        if self._token and self._now() < self._token_expires_at - TOKEN_REFRESH_MARGIN:
            return self._token

        data = parse_envelope(self._http.post(CONNECT_PATH, json=self._credentials)).data
        if not isinstance(data, dict) or not data.get("access_token"):
            raise ResponseFormatError("MISA connect: no access_token in response")
        self._token = data["access_token"]
        expires_at = parse_datetime(str(data.get("expired_time") or ""))
        if expires_at is not None and timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at)
        self._token_expires_at = expires_at or self._now() + DEFAULT_TOKEN_LIFETIME
        return self._token
