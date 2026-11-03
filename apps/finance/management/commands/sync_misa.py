from django.core.management.base import BaseCommand, CommandError

from apps.finance.sync import ENTITIES, run_misa_sync
from apps.integrations.exceptions import IntegrationError
from apps.integrations.reporting import report_runs


class Command(BaseCommand):
    help = "Đọc (chỉ đọc) số dư công nợ/tồn kho từ MISA theo MISA_MODE (mặc định: mock)."

    def add_arguments(self, parser):
        parser.add_argument("--entity", choices=[*ENTITIES, "all"], default="all")

    def handle(self, *args, entity, **options):
        entities = tuple(ENTITIES) if entity == "all" else (entity,)
        try:
            runs = run_misa_sync(entities)
        except IntegrationError as exc:
            raise CommandError(str(exc)) from exc
        report_runs(self, runs)
