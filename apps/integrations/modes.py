"""Integration modes, configured per system in settings/.env.

- mock:     read bundled SIMULATED data (default; no network)
- live:     use the real adapter (only once access is authorized)
- disabled: refuse to sync
"""

from django.core.exceptions import ImproperlyConfigured

from .exceptions import IntegrationDisabled

MOCK, LIVE, DISABLED = "mock", "live", "disabled"
MODES = (MOCK, LIVE, DISABLED)


def resolve(setting_name, value, *, mock_factory, live_factory):
    if value not in MODES:
        raise ImproperlyConfigured(f"{setting_name} must be one of {MODES}, got {value!r}.")
    if value == DISABLED:
        raise IntegrationDisabled(f"Tích hợp đang tắt ({setting_name}=disabled).")
    return mock_factory() if value == MOCK else live_factory()
