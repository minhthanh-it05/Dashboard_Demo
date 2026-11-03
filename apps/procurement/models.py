"""Purchase request tracking.

This records and displays the purchase process for a project; it does not
approve anything. Official approval stays in MISA (CLAUDE.md §4.3, §6.4).
"""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import StatusEntryBase, TrackedModel
from apps.core.utils import next_sequential_code
from apps.projects.models import Project


class PurchaseRequest(TrackedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="purchase_requests")
    request_number = models.CharField(
        "Số đề nghị", max_length=50, unique=True, blank=True, help_text="Bỏ trống để hệ thống tự sinh."
    )
    title = models.CharField("Nội dung đề nghị", max_length=255)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Người đề nghị", on_delete=models.PROTECT, related_name="+"
    )
    request_date = models.DateField("Ngày đề nghị", default=timezone.localdate)
    supplier_name = models.CharField("Nhà cung cấp", max_length=255, blank=True)
    currency = models.CharField("Tiền tệ", max_length=3, default="VND")
    note = models.TextField("Ghi chú", blank=True)
    tracking_closed = models.BooleanField("Đã kết thúc theo dõi", default=False)
    is_demo_data = models.BooleanField("Dữ liệu mẫu", default=False)

    class Meta:
        ordering = ["-request_date", "-id"]
        verbose_name = "Đề nghị mua hàng"
        verbose_name_plural = "Đề nghị mua hàng"

    def __str__(self):
        return f"{self.request_number} – {self.title}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = next_sequential_code(PurchaseRequest, "request_number", "PR")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("procurement:detail", args=[self.project_id, self.pk])

    @property
    def latest_status(self):
        entries = list(self.status_entries.all())
        return entries[0] if entries else None

    @property
    def estimated_total(self):
        totals = [item.line_total for item in self.items.all() if item.line_total is not None]
        return sum(totals) if totals else None


class PurchaseItem(models.Model):
    FINANCE_FIELDS = ("unit_cost",)

    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="items")
    description = models.CharField("Hàng hoá / dịch vụ", max_length=255)
    quantity = models.DecimalField("Số lượng", max_digits=12, decimal_places=2, default=1)
    unit = models.CharField("Đơn vị tính", max_length=30, blank=True)
    unit_cost = models.DecimalField("Đơn giá dự kiến", max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Dòng hàng"
        verbose_name_plural = "Dòng hàng"

    def __str__(self):
        return self.description

    @property
    def line_total(self):
        return None if self.unit_cost is None else self.quantity * self.unit_cost


class PurchaseStatusEntry(StatusEntryBase):
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="status_entries")

    class Meta(StatusEntryBase.Meta):
        verbose_name = "Lịch sử trạng thái mua hàng"
        verbose_name_plural = "Lịch sử trạng thái mua hàng"
