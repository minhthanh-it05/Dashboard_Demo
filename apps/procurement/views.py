from django.views.generic import DetailView

from apps.projects.views import (
    ParentRecordChildCreateView,
    ProjectChildCreateView,
    ProjectChildUpdateView,
    ProjectScopedMixin,
)

from .forms import PurchaseItemForm, PurchaseRequestForm, PurchaseStatusEntryForm
from .models import PurchaseItem, PurchaseRequest, PurchaseStatusEntry


class PurchaseRequestCreateView(ProjectChildCreateView):
    model = PurchaseRequest
    form_class = PurchaseRequestForm
    title = "Tạo đề nghị mua hàng"
    tab = "purchases"

    def prepare(self, obj):
        obj.requester = self.request.user

    def get_success_url(self):
        return self.object.get_absolute_url() if self.object else super().get_success_url()


class PurchaseRequestUpdateView(ProjectChildUpdateView):
    model = PurchaseRequest
    form_class = PurchaseRequestForm
    title = "Sửa đề nghị mua hàng"
    tab = "purchases"


class PurchaseRequestDetailView(ProjectScopedMixin, DetailView):
    manage_required = False
    template_name = "procurement/purchase_detail.html"
    context_object_name = "purchase"

    def get_queryset(self):
        return (
            PurchaseRequest.objects.filter(project=self.project)
            .select_related("requester")
            .prefetch_related("items", "status_entries__recorded_by")
        )


class PurchaseItemCreateView(ParentRecordChildCreateView):
    model = PurchaseItem
    form_class = PurchaseItemForm
    parent_model = PurchaseRequest
    parent_field = "purchase_request"
    title = "Thêm dòng hàng"


class PurchaseStatusCreateView(ParentRecordChildCreateView):
    model = PurchaseStatusEntry
    form_class = PurchaseStatusEntryForm
    parent_model = PurchaseRequest
    parent_field = "purchase_request"
    title = "Ghi nhận trạng thái"

    def prepare(self, obj):
        obj.recorded_by = self.request.user
