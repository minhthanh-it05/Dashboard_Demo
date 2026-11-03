from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.finance import csv_import
from apps.finance.models import FinanceDataKind, ImportStatus


class Command(BaseCommand):
    help = "Nhập file CSV tài chính theo mẫu đề xuất (docs/samples/)."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--kind", required=True, choices=FinanceDataKind.values)
        parser.add_argument("--as-of", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
        parser.add_argument("--period", default="")

    def handle(self, *args, path, kind, as_of, period, **options):
        file_path = Path(path)
        if not file_path.is_file():
            raise CommandError(f"Không tìm thấy file: {path}")

        batch = csv_import.import_file(
            file_path.read_bytes(),
            filename=file_path.name,
            data_kind=kind,
            as_of_date=as_of,
            user=None,
            period_label=period,
        )
        if batch.status == ImportStatus.REJECTED:
            for error in batch.errors:
                self.stderr.write(f"  - {error}")
            raise CommandError("File bị từ chối; không có dữ liệu nào được nhập.")
        self.stdout.write(self.style.SUCCESS(f"Đã nhập {batch.row_count} dòng: {batch}"))
