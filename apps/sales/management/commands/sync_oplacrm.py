from django.core.management.base import BaseCommand, CommandError

from apps.integrations.exceptions import IntegrationError
from apps.integrations.reporting import report_runs
from apps.sales.sync import ENTITIES, run_oplacrm_sync


class Command(BaseCommand):
    help = "Đồng bộ (chỉ đọc) Accounts/Opportunities từ OplaCRM theo OPLACRM_MODE (mặc định: mock)."

    def add_arguments(self, parser):
        parser.add_argument("--entity", choices=[*ENTITIES, "all"], default="all")

    def handle(self, *args, entity, **options):
        entities = tuple(ENTITIES) if entity == "all" else (entity,)
        try:
            runs = run_oplacrm_sync(entities)
        except IntegrationError as exc:
            raise CommandError(str(exc)) from exc
        report_runs(self, runs)
