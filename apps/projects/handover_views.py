from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from apps.accounts.roles import can_view_handovers, is_project_manager
from apps.core import audit
from apps.core.models import AuditLog

from . import services
from .forms import HandoverReviewForm, ProjectForm, SalesHandoverForm
from .models import HandoverStatus, Project, ProjectStatus, SalesHandover
from .views import PMRequiredMixin


class HandoverViewerMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return can_view_handovers(self.request.user)


class HandoverListView(HandoverViewerMixin, ListView):
    template_name = "projects/handover_list.html"
    context_object_name = "handovers"
    paginate_by = 25

    def get_queryset(self):
        qs = SalesHandover.objects.select_related("reviewed_by", "project")
        status = self.request.GET.get("status")
        if status in HandoverStatus.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(status_choices=HandoverStatus.choices, current_status=self.request.GET.get("status", ""))
        return context


class HandoverDetailView(HandoverViewerMixin, DetailView):
    model = SalesHandover
    template_name = "projects/handover_detail.html"
    context_object_name = "handover"


class HandoverCreateView(PMRequiredMixin, CreateView):
    """Phase 1: a PM enters the handover manually on Sales' behalf (assumption)."""

    model = SalesHandover
    form_class = SalesHandoverForm
    template_name = "core/form.html"
    extra_context = {"title": "Nhập hồ sơ bàn giao từ Sales"}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        handover = form.save(commit=False)
        handover.created_by = handover.updated_by = self.request.user
        handover.save()
        audit.record(self.request.user, handover, AuditLog.Action.CREATE, audit.snapshot(handover))
        messages.success(self.request, "Đã lưu hồ sơ bàn giao.")
        return redirect(handover)


class HandoverUpdateView(PMRequiredMixin, UpdateView):
    model = SalesHandover
    form_class = SalesHandoverForm
    template_name = "core/form.html"
    extra_context = {"title": "Sửa hồ sơ bàn giao"}

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self._before = audit.snapshot(obj)
        return obj

    def dispatch(self, request, *args, **kwargs):
        if not is_project_manager(request.user):
            return super().dispatch(request, *args, **kwargs)  # login redirect / 403
        handover = get_object_or_404(SalesHandover, pk=kwargs["pk"])
        if handover.linked_project is not None:
            messages.warning(request, "Bàn giao đã có dự án nên không sửa được nữa.")
            return redirect(handover)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        handover = form.save(commit=False)
        handover.updated_by = self.request.user
        handover.save()
        changes = audit.diff(self._before, audit.snapshot(handover))
        if changes:
            audit.record(self.request.user, handover, AuditLog.Action.UPDATE, changes)
        messages.success(self.request, "Đã cập nhật hồ sơ bàn giao.")
        return redirect(handover)


class HandoverReviewView(PMRequiredMixin, FormView):
    form_class = HandoverReviewForm
    template_name = "core/form.html"

    def dispatch(self, request, *args, **kwargs):
        self.handover = get_object_or_404(SalesHandover, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {"review_note": self.handover.review_note}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(title=f"Tiếp nhận bàn giao: {self.handover}", cancel_url=self.handover.get_absolute_url())
        return context

    def form_valid(self, form):
        try:
            services.review_handover(
                self.handover, self.request.user, form.cleaned_data["status"], form.cleaned_data["review_note"]
            )
        except ValidationError as exc:
            messages.error(self.request, " ".join(exc.messages))
        else:
            messages.success(self.request, "Đã ghi nhận kết quả tiếp nhận.")
        return redirect(self.handover)


class HandoverCreateProjectView(PMRequiredMixin, CreateView):
    """Create the Project from an ACCEPTED handover (at most one per handover)."""

    model = Project
    form_class = ProjectForm
    template_name = "core/form.html"

    def dispatch(self, request, *args, **kwargs):
        self.handover = get_object_or_404(SalesHandover, pk=kwargs["pk"])
        if is_project_manager(request.user) and (
            self.handover.status != HandoverStatus.ACCEPTED or self.handover.linked_project is not None
        ):
            messages.error(request, "Chỉ tạo dự án từ bàn giao đã chấp nhận và chưa có dự án.")
            return redirect(self.handover)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        # Execution dates start from the Sales commitment but are the PM's
        # plan from here on; they are stored separately from committed_*.
        return {
            "name": self.handover.deal_name,
            "customer_name": self.handover.customer_name,
            "manager": self.request.user,
            "status": ProjectStatus.READY,
            "planned_start_date": self.handover.committed_start_date,
            "planned_end_date": self.handover.committed_end_date,
        }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(title=f"Tạo dự án từ bàn giao: {self.handover}", cancel_url=self.handover.get_absolute_url())
        return context

    def form_valid(self, form):
        try:
            project = services.create_project_from_handover(self.handover, self.request.user, form.save(commit=False))
        except ValidationError as exc:
            messages.error(self.request, " ".join(exc.messages))
            return redirect(self.handover)
        messages.success(self.request, f"Đã tạo dự án {project.code}.")
        return redirect(project)
