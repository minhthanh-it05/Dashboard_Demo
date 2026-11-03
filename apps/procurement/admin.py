from django.contrib import admin

from .models import PurchaseItem, PurchaseRequest, PurchaseStatusEntry


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0


class PurchaseStatusEntryInline(admin.TabularInline):
    model = PurchaseStatusEntry
    extra = 0
    readonly_fields = ("status_label", "status_source", "evidence_note", "recorded_by", "recorded_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("request_number", "title", "project", "request_date", "tracking_closed", "is_demo_data")
    list_filter = ("tracking_closed", "is_demo_data")
    search_fields = ("request_number", "title", "supplier_name")
    inlines = [PurchaseItemInline, PurchaseStatusEntryInline]
