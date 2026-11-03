"""Live OplaCRM adapter — placeholder until access is authorized.

TODO(Phase 2), once confirmed with the vendor/company (docs/OPEN_QUESTIONS.md, section D):
- tenant has API access; authentication method and required credentials
- endpoint paths, pagination and incremental-sync fields for Accounts/Opportunities
- response schema, and which stage means "Won"
Then: build requests with apps.integrations.http.JsonHttpClient and map
responses into apps.integrations.records. Nothing here calls the network.
"""

from django.conf import settings

from apps.integrations.exceptions import IntegrationNotReady
from apps.integrations.models import SyncMode

NOT_READY = (
    "OplaCRM live chưa sẵn sàng: chưa xác nhận quyền API, cách xác thực và schema dữ liệu. "
    "Dùng OPLACRM_MODE=mock cho tới khi được cấp quyền."
)


class LiveOplaCRMProvider:
    mode = SyncMode.LIVE

    @classmethod
    def from_settings(cls):
        if not settings.OPLACRM_BASE_URL:
            raise IntegrationNotReady("Thiếu OPLACRM_BASE_URL. " + NOT_READY)
        return cls()

    def iter_accounts(self, updated_since):
        raise IntegrationNotReady(NOT_READY)

    def iter_opportunities(self, updated_since):
        raise IntegrationNotReady(NOT_READY)
