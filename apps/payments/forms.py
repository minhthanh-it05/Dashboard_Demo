from apps.procurement.forms import StatusEntryFormMixin
from apps.procurement.models import PurchaseRequest
from apps.projects.forms import ScopedModelForm

from .models import PaymentRequest, PaymentStatusEntry


class PaymentRequestForm(ScopedModelForm):
    finance_fields = PaymentRequest.FINANCE_FIELDS

    class Meta:
        model = PaymentRequest
        fields = [
            "request_number",
            "payee_name",
            "amount",
            "currency",
            "reason",
            "purchase_request",
            "request_date",
            "tracking_closed",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_request"].queryset = PurchaseRequest.objects.filter(project=self.project)


class PaymentStatusEntryForm(StatusEntryFormMixin, ScopedModelForm):
    class Meta:
        model = PaymentStatusEntry
        fields = ["status_label", "status_source", "evidence_note"]
