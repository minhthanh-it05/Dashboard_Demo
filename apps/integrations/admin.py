from django.contrib import admin

from .models import SyncRun, SyncState


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SyncRun)
class SyncRunAdmin(ReadOnlyAdmin):
    list_display = ("started_at", "system", "entity", "mode", "status", "fetched", "created", "updated", "failed")
    list_filter = ("system", "entity", "mode", "status")


@admin.register(SyncState)
class SyncStateAdmin(ReadOnlyAdmin):
    list_display = ("system", "entity", "cursor", "last_success_at", "last_run")
