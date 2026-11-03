from django.views.generic import DetailView

from apps.projects.views import (
    ParentRecordChildCreateView,
    ProjectChildCreateView,
    ProjectChildUpdateView,
    ProjectScopedMixin,
)

from .forms import PaymentRequestForm, PaymentStatusEntryForm
from .models import PaymentRequest, PaymentStatusEntry


class PaymentRequestCreateView(ProjectChildCreateView):
    model = PaymentRequest
    form_class = PaymentRequestForm
    title = "Tạo đề nghị thanh toán"
    tab = "payments"

    def prepare(self, obj):
        obj.requester = self.request.user

    def get_success_url(self):
        return self.object.get_absolute_url() if self.object else super().get_success_url()


class PaymentRequestUpdateView(ProjectChildUpdateView):
    model = PaymentRequest
    form_class = PaymentRequestForm
    title = "Sửa đề nghị thanh toán"
    tab = "payments"


class PaymentRequestDetailView(ProjectScopedMixin, DetailView):
    manage_required = False
    template_name = "payments/payment_detail.html"
    context_object_name = "payment"

    def get_queryset(self):
        return (
            PaymentRequest.objects.filter(project=self.project)
            .select_related("requester", "purchase_request")
            .prefetch_related("status_entries__recorded_by")
        )


class PaymentStatusCreateView(ParentRecordChildCreateView):
    model = PaymentStatusEntry
    form_class = PaymentStatusEntryForm
    parent_model = PaymentRequest
    parent_field = "payment_request"
    title = "Ghi nhận trạng thái"

    def prepare(self, obj):
        obj.recorded_by = self.request.user
