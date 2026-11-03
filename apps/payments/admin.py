from django.contrib import admin

from .models import PaymentRequest, PaymentStatusEntry


class PaymentStatusEntryInline(admin.TabularInline):
    model = PaymentStatusEntry
    extra = 0
    readonly_fields = ("status_label", "status_source", "evidence_note", "recorded_by", "recorded_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ("request_number", "payee_name", "project", "request_date", "tracking_closed", "is_demo_data")
    list_filter = ("tracking_closed", "is_demo_data")
    search_fields = ("request_number", "payee_name")
    inlines = [PaymentStatusEntryInline]
