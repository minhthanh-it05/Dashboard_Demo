from django.contrib import admin

from .models import (
    KickoffRecord,
    ProgressUpdate,
    Project,
    ProjectContract,
    ProjectDocument,
    ProjectIssue,
    ProjectMember,
    ProjectMilestone,
    ProjectTask,
    SalesHandover,
)


@admin.register(SalesHandover)
class SalesHandoverAdmin(admin.ModelAdmin):
    list_display = ("deal_name", "customer_name", "status", "external_opportunity_id", "is_demo_data")
    list_filter = ("status", "source_system", "is_demo_data")
    search_fields = ("deal_name", "customer_name", "external_opportunity_id")


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "customer_name", "status", "manager", "planned_end_date", "is_demo_data")
    list_filter = ("status", "is_demo_data")
    search_fields = ("code", "name", "customer_name")
    inlines = [ProjectMemberInline]


@admin.register(ProjectMilestone)
class ProjectMilestoneAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "due_date", "status")
    list_filter = ("status",)


@admin.register(ProjectTask)
class ProjectTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "assignee", "due_date", "status", "priority")
    list_filter = ("status", "priority")
    search_fields = ("title",)


@admin.register(ProgressUpdate)
class ProgressUpdateAdmin(admin.ModelAdmin):
    """History is append-only, so it is read-only in admin too."""

    list_display = ("created_at", "project", "task", "author", "percent", "status_from", "status_to")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProjectIssue)
class ProjectIssueAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "kind", "severity", "status", "assignee")
    list_filter = ("kind", "severity", "status")


admin.site.register(KickoffRecord)
admin.site.register(ProjectContract)
admin.site.register(ProjectDocument)
