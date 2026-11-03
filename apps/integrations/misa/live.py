"""Live MISA adapter: wires the ACT client, but row mapping is not done yet.

TODO(Phase 3), once MISA confirms (docs/OPEN_QUESTIONS.md, section E):
- which API applies to the subscription (AMISKT Developer Portal vs ACT Open API)
- the row schema of get_list_acc_obj_debt / get_list_inventory_balance
Then implement _map_debt_row / _map_inventory_row and flip ROW_SCHEMA_CONFIRMED.
Until then the provider refuses before making any network call.
"""

from django.conf import settings

from apps.integrations.exceptions import IntegrationNotReady
from apps.integrations.http import JsonHttpClient
from apps.integrations.models import SyncMode

from .act_client import MisaActClient

ROW_SCHEMA_CONFIRMED = False

NOT_READY = (
    "MISA live chưa sẵn sàng: chưa xác nhận API áp dụng cho gói dịch vụ và schema dữ liệu trả về. "
    "Dùng MISA_MODE=mock hoặc nhập file CSV cho tới khi MISA xác nhận."
)
REQUIRED_SETTINGS = ("MISA_ACT_BASE_URL", "MISA_APP_ID", "MISA_ACCESS_CODE", "MISA_ORG_COMPANY_CODE")


class LiveMisaProvider:
    mode = SyncMode.LIVE

    def __init__(self, client):
        self._client = client

    @classmethod
    def from_settings(cls):
        missing = [name for name in REQUIRED_SETTINGS if not getattr(settings, name)]
        if missing:
            raise IntegrationNotReady(f"Thiếu cấu hình: {', '.join(missing)}. {NOT_READY}")
        http = JsonHttpClient(
            settings.MISA_ACT_BASE_URL,
            timeout_seconds=settings.INTEGRATION_HTTP_TIMEOUT_SECONDS,
            min_interval_seconds=settings.MISA_MIN_REQUEST_INTERVAL_SECONDS,
        )
        client = MisaActClient(
            http,
            app_id=settings.MISA_APP_ID,
            access_code=settings.MISA_ACCESS_CODE,
            org_company_code=settings.MISA_ORG_COMPANY_CODE,
        )
        return cls(client)

    def fetch_debt_balances(self):
        self._ensure_ready()
        return [_map_debt_row(row) for row in self._client.iter_rows("get_list_acc_obj_debt")]

    def fetch_inventory_balances(self):
        self._ensure_ready()
        return [_map_inventory_row(row) for row in self._client.iter_rows("get_list_inventory_balance")]

    @staticmethod
    def _ensure_ready():
        if not ROW_SCHEMA_CONFIRMED:
            raise IntegrationNotReady(NOT_READY)


def _map_debt_row(row):
    raise NotImplementedError("TODO(Phase 3): map confirmed MISA debt fields to DebtBalanceRecord")


def _map_inventory_row(row):
    raise NotImplementedError("TODO(Phase 3): map confirmed MISA inventory fields to InventoryBalanceRecord")
