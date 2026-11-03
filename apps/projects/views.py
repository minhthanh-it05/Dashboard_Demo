from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from apps.accounts.roles import is_project_manager
from apps.core import audit
from apps.core.models import AuditLog

from . import services
from .forms import (
    ContractForm,
    DocumentForm,
    IssueForm,
    KickoffForm,
    MilestoneForm,
    ProgressUpdateForm,
    ProjectForm,
    ProjectMemberForm,
    TaskForm,
    TaskStatusForm,
)
from .models import (
    KickoffRecord,
    ProgressUpdate,
    Project,
    ProjectContract,
    ProjectDocument,
    ProjectIssue,
    ProjectMember,
    ProjectMilestone,
    ProjectStatus,
    ProjectTask,
)
from .permissions import can_edit_issue, can_manage_project, can_update_task, visible_projects


def latest_project_percent():
    """Most recent project-level percent reported by a user (no formula)."""
    return Subquery(
        ProgressUpdate.objects.filter(project=OuterRef("pk"), task__isnull=True, percent__isnull=False)
        .order_by("-created_at")
        .values("percent")[:1]
    )


class PMRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_project_manager(self.request.user)


class ProjectScopedMixin(LoginRequiredMixin):
    """Load `self.project` from the URL, 404 if the user cannot see it.

    With `manage_required = True` the user must also be allowed to manage it.
    """

    manage_required = True

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.project = get_object_or_404(visible_projects(request.user), pk=kwargs["project_pk"])
        if self.manage_required and not can_manage_project(request.user, self.project):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.project
        return context


class ProjectChildFormMixin(ProjectScopedMixin):
    template_name = "core/form.html"
    title = ""
    tab = ""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(project=self.project, user=self.request.user)
        return kwargs

    def get_success_url(self):
        url = self.project.get_absolute_url()
        return f"{url}#{self.tab}" if self.tab else url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(title=self.title, cancel_url=self.get_success_url())
        return context


class ProjectChildCreateView(ProjectChildFormMixin, CreateView):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.model(project=self.project)
        return kwargs

    def prepare(self, obj):
        """Hook for setting non-form fields before the first save."""

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.project = self.project
        if hasattr(obj, "created_by_id"):
            obj.created_by = obj.updated_by = self.request.user
        self.prepare(obj)
        obj.save()
        form.save_m2m()
        self.object = obj
        audit.record(self.request.user, obj, AuditLog.Action.CREATE, audit.snapshot(obj))
        messages.success(self.request, f"Đã tạo: {obj}")
        return redirect(self.get_success_url())


class ProjectChildUpdateView(ProjectChildFormMixin, UpdateView):
    def get_queryset(self):
        return self.model.objects.filter(project=self.project)

    def check_object(self, obj):
        """Hook for extra object-level permission checks."""

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.check_object(obj)
        self._before = audit.snapshot(obj)
        return obj

    def form_valid(self, form):
        obj = form.save(commit=False)
        if hasattr(obj, "updated_by_id"):
            obj.updated_by = self.request.user
        obj.save()
        form.save_m2m()
        changes = audit.diff(self._before, audit.snapshot(obj))
        if changes:
            audit.record(self.request.user, obj, AuditLog.Action.UPDATE, changes)
        messages.success(self.request, f"Đã cập nhật: {obj}")
        return redirect(self.get_success_url())


class ParentRecordChildCreateView(ProjectScopedMixin, CreateView):
    """Create a row (line item, status entry) under a project-scoped record
    such as a purchase or payment request. URL kwarg `pk` is the parent."""

    template_name = "core/form.html"
    parent_model = None
    parent_field = ""
    title = ""

    def get_parent(self):
        if not hasattr(self, "_parent"):
            self._parent = get_object_or_404(self.parent_model, project=self.project, pk=self.kwargs["pk"])
        return self._parent

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(user=self.request.user, instance=self.model(**{self.parent_field: self.get_parent()}))
        return kwargs

    def get_success_url(self):
        return self.get_parent().get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(title=f"{self.title}: {self.get_parent()}", cancel_url=self.get_success_url())
        return context

    def prepare(self, obj):
        """Hook for setting non-form fields before saving."""

    def form_valid(self, form):
        obj = form.save(commit=False)
        setattr(obj, self.parent_field, self.get_parent())
        self.prepare(obj)
        obj.save()
        self.object = obj
        audit.record(self.request.user, obj, AuditLog.Action.CREATE, audit.snapshot(obj))
        messages.success(self.request, "Đã lưu.")
        return redirect(self.get_success_url())


# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------


class ProjectListView(LoginRequiredMixin, ListView):
    template_name = "projects/project_list.html"
    context_object_name = "projects"
    paginate_by = 25

    def get_queryset(self):
        qs = visible_projects(self.request.user).select_related("manager").annotate(latest_percent=latest_project_percent())
        status = self.request.GET.get("status")
        if status in ProjectStatus.values:
            qs = qs.filter(status=status)
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(customer_name__icontains=query))
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            status_choices=ProjectStatus.choices,
            current_status=self.request.GET.get("status", ""),
            query=self.request.GET.get("q", ""),
        )
        return context


class ProjectCreateView(PMRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "core/form.html"
    extra_context = {"title": "Tạo dự án"}

    def get_initial(self):
        return {"manager": self.request.user}

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        project = form.save(commit=False)
        project.created_by = project.updated_by = self.request.user
        project.save()
        audit.record(self.request.user, project, AuditLog.Action.CREATE, audit.snapshot(project))
        messages.success(self.request, f"Đã tạo dự án {project.code}.")
        return redirect(project)


class ProjectUpdateView(PMRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "core/form.html"
    extra_context = {"title": "Sửa thông tin dự án"}

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self._before = audit.snapshot(obj)
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        project = form.save(commit=False)
        project.updated_by = self.request.user
        project.save()
        changes = audit.diff(self._before, audit.snapshot(project))
        if changes:
            audit.record(self.request.user, project, AuditLog.Action.UPDATE, changes)
        messages.success(self.request, "Đã cập nhật dự án.")
        return redirect(project)


class ProjectDetailView(LoginRequiredMixin, DetailView):
    template_name = "projects/project_detail.html"
    context_object_name = "project"

    def get_queryset(self):
        return (
            visible_projects(self.request.user)
            .select_related("manager", "handover")
            .annotate(latest_percent=latest_project_percent())
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        user = self.request.user
        tasks = project.tasks.select_related("assignee", "milestone")
        context.update(
            can_manage=can_manage_project(user, project),
            members=project.members.select_related("user"),
            milestones=project.milestones.all(),
            tasks=tasks,
            my_task_ids={t.pk for t in tasks if t.assignee_id == user.pk},
            progress_updates=project.progress_updates.select_related("author", "task")[:30],
            issues=project.issues.select_related("assignee", "reported_by", "task"),
            kickoffs=project.kickoffs.all(),
            contracts=project.contracts.select_related("document"),
            documents=project.documents.all(),
            purchase_requests=project.purchase_requests.select_related("requester").prefetch_related(
                "status_entries", "items"
            ),
            payment_requests=project.payment_requests.select_related("requester").prefetch_related("status_entries"),
        )
        return context


class MemberAddView(ProjectChildCreateView):
    model = ProjectMember
    form_class = ProjectMemberForm
    title = "Thêm thành viên"
    tab = "members"


class MemberRemoveView(ProjectScopedMixin, View):
    def post(self, request, project_pk, pk):
        member = get_object_or_404(ProjectMember, project=self.project, pk=pk)
        audit.record(request.user, member, AuditLog.Action.DELETE, audit.snapshot(member))
        member.delete()
        messages.success(request, "Đã xoá thành viên khỏi dự án.")
        return redirect(f"{self.project.get_absolute_url()}#members")


# --------------------------------------------------------------------------
# Plan
# --------------------------------------------------------------------------


class MilestoneCreateView(ProjectChildCreateView):
    model = ProjectMilestone
    form_class = MilestoneForm
    title = "Thêm mốc tiến độ"
    tab = "plan"


class MilestoneUpdateView(ProjectChildUpdateView):
    model = ProjectMilestone
    form_class = MilestoneForm
    title = "Sửa mốc tiến độ"
    tab = "plan"


class TaskCreateView(ProjectChildCreateView):
    model = ProjectTask
    form_class = TaskForm
    title = "Thêm công việc"
    tab = "plan"


class TaskUpdateView(ProjectChildUpdateView):
    model = ProjectTask
    form_class = TaskForm
    title = "Sửa công việc"
    tab = "plan"


class TaskStatusView(ProjectScopedMixin, FormView):
    """Members change the status of their own tasks here; PMs any task."""

    manage_required = False
    form_class = TaskStatusForm
    template_name = "core/form.html"

    def get_task(self):
        if not hasattr(self, "_task"):
            self._task = get_object_or_404(ProjectTask, project=self.project, pk=self.kwargs["pk"])
            if not can_update_task(self.request.user, self._task):
                raise PermissionDenied
        return self._task

    def get_initial(self):
        return {"status": self.get_task().status}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            title=f"Cập nhật trạng thái: {self.get_task().title}",
            cancel_url=f"{self.project.get_absolute_url()}#plan",
        )
        return context

    def form_valid(self, form):
        services.change_task_status(
            self.get_task(),
            form.cleaned_data["status"],
            self.request.user,
            note=form.cleaned_data["note"].strip(),
            percent=form.cleaned_data["percent"],
        )
        messages.success(self.request, "Đã cập nhật trạng thái công việc.")
        return redirect(f"{self.project.get_absolute_url()}#plan")


# --------------------------------------------------------------------------
# Progress and issues
# --------------------------------------------------------------------------


class ProgressUpdateCreateView(ProjectChildCreateView):
    manage_required = False
    model = ProgressUpdate
    form_class = ProgressUpdateForm
    title = "Gửi cập nhật tiến độ"
    tab = "progress"

    def prepare(self, obj):
        obj.author = self.request.user


class IssueCreateView(ProjectChildCreateView):
    manage_required = False
    model = ProjectIssue
    form_class = IssueForm
    title = "Báo cáo vấn đề / rủi ro"
    tab = "issues"

    def prepare(self, obj):
        obj.reported_by = self.request.user


class IssueUpdateView(ProjectChildUpdateView):
    manage_required = False
    model = ProjectIssue
    form_class = IssueForm
    title = "Cập nhật vấn đề / rủi ro"
    tab = "issues"

    def check_object(self, obj):
        if not can_edit_issue(self.request.user, obj):
            raise PermissionDenied


# --------------------------------------------------------------------------
# Kickoff, contracts, documents
# --------------------------------------------------------------------------


class KickoffCreateView(ProjectChildCreateView):
    model = KickoffRecord
    form_class = KickoffForm
    title = "Thêm biên bản kickoff"
    tab = "records"


class KickoffUpdateView(ProjectChildUpdateView):
    model = KickoffRecord
    form_class = KickoffForm
    title = "Sửa biên bản kickoff"
    tab = "records"


class ContractCreateView(ProjectChildCreateView):
    model = ProjectContract
    form_class = ContractForm
    title = "Thêm thông tin hợp đồng"
    tab = "records"


class ContractUpdateView(ProjectChildUpdateView):
    model = ProjectContract
    form_class = ContractForm
    title = "Sửa thông tin hợp đồng"
    tab = "records"


class DocumentCreateView(ProjectChildCreateView):
    model = ProjectDocument
    form_class = DocumentForm
    title = "Thêm tài liệu"
    tab = "records"


class DocumentUpdateView(ProjectChildUpdateView):
    model = ProjectDocument
    form_class = DocumentForm
    title = "Sửa tài liệu"
    tab = "records"
