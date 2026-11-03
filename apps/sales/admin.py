from django.contrib import admin

from .models import SalesAccount, SalesOpportunity


class SyncedRecordAdmin(admin.ModelAdmin):
    """Synced rows are owned by OplaCRM; edit them there, not here."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SalesAccount)
class SalesAccountAdmin(SyncedRecordAdmin):
    list_display = ("name", "external_id", "source_system", "last_synced_at", "is_simulated")
    search_fields = ("name", "external_id")


@admin.register(SalesOpportunity)
class SalesOpportunityAdmin(SyncedRecordAdmin):
    list_display = ("name", "account", "stage_name", "is_won", "last_synced_at", "is_simulated")
    list_filter = ("is_won", "is_simulated")
    search_fields = ("name", "external_id")
