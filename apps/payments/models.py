"""Payment request tracking.

Tracks a request and the statuses users report; it never executes or
approves a payment. MISA remains the official source (CLAUDE.md §4.4, §6.5).
"""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.models import StatusEntryBase, TrackedModel
from apps.core.utils import next_sequential_code
from apps.procurement.models import PurchaseRequest
from apps.projects.models import Project


class PaymentRequest(TrackedModel):
    FINANCE_FIELDS = ("amount",)

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="payment_requests")
    request_number = models.CharField(
        "Số đề nghị", max_length=50, unique=True, blank=True, help_text="Bỏ trống để hệ thống tự sinh."
    )
    payee_name = models.CharField("Đơn vị / người nhận", max_length=255)
    amount = models.DecimalField("Số tiền", max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField("Tiền tệ", max_length=3, default="VND")
    reason = models.TextField("Lý do / mốc thanh toán")
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        verbose_name="Đề nghị mua hàng liên quan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_requests",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Người đề nghị", on_delete=models.PROTECT, related_name="+"
    )
    request_date = models.DateField("Ngày đề nghị", default=timezone.localdate)
    tracking_closed = models.BooleanField("Đã kết thúc theo dõi", default=False)
    is_demo_data = models.BooleanField("Dữ liệu mẫu", default=False)

    class Meta:
        ordering = ["-request_date", "-id"]
        verbose_name = "Đề nghị thanh toán"
        verbose_name_plural = "Đề nghị thanh toán"

    def __str__(self):
        return f"{self.request_number} – {self.payee_name}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = next_sequential_code(PaymentRequest, "request_number", "PAY")
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("payments:detail", args=[self.project_id, self.pk])

    @property
    def latest_status(self):
        entries = list(self.status_entries.all())
        return entries[0] if entries else None


class PaymentStatusEntry(StatusEntryBase):
    payment_request = models.ForeignKey(PaymentRequest, on_delete=models.CASCADE, related_name="status_entries")

    class Meta(StatusEntryBase.Meta):
        verbose_name = "Lịch sử trạng thái thanh toán"
        verbose_name_plural = "Lịch sử trạng thái thanh toán"
