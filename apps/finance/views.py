from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, TemplateView

from apps.accounts.roles import can_import_finance, can_view_finance

from . import csv_import, services
from .forms import FinanceCsvImportForm
from .models import FinanceDataKind, FinanceImportBatch, ImportStatus


class FinanceViewerMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_view_finance(self.request.user)


class FinanceOverviewView(FinanceViewerMixin, TemplateView):
    template_name = "finance/overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        debt_batch = services.current_batch(FinanceDataKind.DEBT_BALANCE)
        inventory_batch = services.current_batch(FinanceDataKind.INVENTORY_BALANCE)
        context.update(
            debt_batch=debt_batch,
            debt_rows=debt_batch.debt_rows.all() if debt_batch else [],
            inventory_batch=inventory_batch,
            inventory_rows=inventory_batch.inventory_rows.all() if inventory_batch else [],
            recent_batches=FinanceImportBatch.objects.select_related("imported_by")[:15],
        )
        return context


class FinanceBatchDetailView(FinanceViewerMixin, DetailView):
    model = FinanceImportBatch
    template_name = "finance/batch_detail.html"
    context_object_name = "batch"


class FinanceCsvImportView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    form_class = FinanceCsvImportForm
    template_name = "core/form.html"
    extra_context = {"title": "Nhập file CSV tài chính", "cancel_url": reverse_lazy("finance:overview")}

    def test_func(self):
        return can_import_finance(self.request.user)

    def form_valid(self, form):
        data = form.cleaned_data
        batch = csv_import.import_file(
            data["file"].read(),
            filename=data["file"].name,
            data_kind=data["data_kind"],
            as_of_date=data["as_of_date"],
            user=self.request.user,
            period_label=data["period_label"],
        )
        if batch.status == ImportStatus.IMPORTED:
            messages.success(self.request, f"Đã nhập {batch.row_count} dòng.")
        else:
            messages.error(self.request, "File bị từ chối; không có dữ liệu nào được nhập. Xem chi tiết lỗi bên dưới.")
        return redirect("finance:batch_detail", pk=batch.pk)
