"""Finance snapshots read from MISA or imported from approved files.

Balances are per counterparty (customer/supplier). They are deliberately NOT
linked to projects: no reliable project mapping exists yet (CLAUDE.md §5.2).
Every batch records its provenance (CLAUDE.md §7.2).
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import SourceSystem


class FinanceDataKind(models.TextChoices):
    DEBT_BALANCE = "DEBT_BALANCE", "Số dư công nợ theo đối tượng"
    INVENTORY_BALANCE = "INVENTORY_BALANCE", "Tồn kho theo kho"


class ImportStatus(models.TextChoices):
    IMPORTED = "IMPORTED", "Đã nhập"
    REJECTED = "REJECTED", "Bị từ chối"


class FinanceImportBatch(models.Model):
    """One snapshot of one kind of finance data.

    Exactly one IMPORTED batch per kind is `is_current`; a newer batch
    supersedes the older one, so re-running a sync never duplicates data.
    """

    source_system = models.CharField("Nguồn", max_length=20, choices=SourceSystem.choices)
    data_kind = models.CharField("Loại dữ liệu", max_length=20, choices=FinanceDataKind.choices)
    status = models.CharField("Kết quả", max_length=10, choices=ImportStatus.choices)
    as_of_date = models.DateField("Số liệu tại ngày")
    period_label = models.CharField("Kỳ dữ liệu", max_length=50, blank=True)
    source_filename = models.CharField("Tên file", max_length=255, blank=True)
    file_sha256 = models.CharField("Mã băm file", max_length=64, blank=True, db_index=True)
    row_count = models.PositiveIntegerField("Số dòng", default=0)
    errors = models.JSONField("Lỗi kiểm tra", default=list, blank=True)
    is_current = models.BooleanField("Đang hiệu lực", default=False)
    is_simulated = models.BooleanField("Dữ liệu mô phỏng", default=False)
    sync_run = models.ForeignKey(
        "integrations.SyncRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="finance_batches"
    )
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người nhập",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    imported_at = models.DateTimeField("Thời điểm nhập", auto_now_add=True)

    class Meta:
        ordering = ["-imported_at", "-id"]
        verbose_name = "Lô dữ liệu tài chính"
        verbose_name_plural = "Lô dữ liệu tài chính"
        constraints = [
            models.UniqueConstraint(
                fields=["data_kind"], condition=Q(is_current=True), name="uniq_current_finance_batch_per_kind"
            )
        ]

    def __str__(self):
        return f"{self.get_data_kind_display()} @ {self.as_of_date:%d/%m/%Y} ({self.get_source_system_display()})"


class DebtBalanceSnapshot(models.Model):
    batch = models.ForeignKey(FinanceImportBatch, on_delete=models.CASCADE, related_name="debt_rows")
    counterparty_code = models.CharField("Mã đối tượng", max_length=100)
    counterparty_name = models.CharField("Tên đối tượng", max_length=255)
    receivable_amount = models.DecimalField("Phải thu", max_digits=18, decimal_places=2, null=True, blank=True)
    payable_amount = models.DecimalField("Phải trả", max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField("Tiền tệ", max_length=3, default="VND")

    class Meta:
        ordering = ["counterparty_code"]
        verbose_name = "Số dư công nợ"
        verbose_name_plural = "Số dư công nợ"
        constraints = [
            models.UniqueConstraint(fields=["batch", "counterparty_code"], name="uniq_debt_row_per_batch")
        ]

    def __str__(self):
        return self.counterparty_name


class InventoryBalanceSnapshot(models.Model):
    batch = models.ForeignKey(FinanceImportBatch, on_delete=models.CASCADE, related_name="inventory_rows")
    item_code = models.CharField("Mã hàng", max_length=100)
    item_name = models.CharField("Tên hàng", max_length=255)
    warehouse_code = models.CharField("Mã kho", max_length=100)
    quantity = models.DecimalField("Số lượng", max_digits=18, decimal_places=3)
    unit = models.CharField("Đơn vị tính", max_length=30, blank=True)
    amount = models.DecimalField("Giá trị", max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["warehouse_code", "item_code"]
        verbose_name = "Tồn kho"
        verbose_name_plural = "Tồn kho"
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "item_code", "warehouse_code"], name="uniq_inventory_row_per_batch"
            )
        ]

    def __str__(self):
        return f"{self.item_code} @ {self.warehouse_code}"


ROW_MODELS = {
    FinanceDataKind.DEBT_BALANCE: DebtBalanceSnapshot,
    FinanceDataKind.INVENTORY_BALANCE: InventoryBalanceSnapshot,
}
