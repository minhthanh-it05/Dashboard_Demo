from django.contrib import admin

from .models import DebtBalanceSnapshot, FinanceImportBatch, InventoryBalanceSnapshot


@admin.register(FinanceImportBatch)
class FinanceImportBatchAdmin(admin.ModelAdmin):
    """Snapshots are history; correct data by importing a new batch."""

    list_display = ("imported_at", "data_kind", "source_system", "status", "as_of_date", "row_count", "is_current", "is_simulated")
    list_filter = ("data_kind", "source_system", "status", "is_current", "is_simulated")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(DebtBalanceSnapshot)
admin.site.register(InventoryBalanceSnapshot)
