from django.apps import AppConfig


class FinanceConfig(AppConfig):
    name = "apps.finance"
    verbose_name = "Dữ liệu tài chính (MISA / file)"

    def ready(self):
        from apps.integrations import jobs
        from apps.integrations.models import ExternalSystem

        from .sync import run_misa_sync

        jobs.register(
            jobs.SyncJob(
                key="misa",
                label="MISA → Công nợ, Tồn kho",
                system=ExternalSystem.MISA_ACT,
                run=run_misa_sync,
            )
        )
