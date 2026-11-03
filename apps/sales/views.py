from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.views.generic import ListView

from apps.accounts.roles import can_view_sales_data
from apps.integrations.models import ExternalSystem, SyncState

from .models import SalesOpportunity


class OpportunityListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = "sales/opportunity_list.html"
    context_object_name = "opportunities"
    paginate_by = 25

    def test_func(self):
        return can_view_sales_data(self.request.user)

    def get_queryset(self):
        qs = SalesOpportunity.objects.select_related("account")
        if self.request.GET.get("won") == "1":
            qs = qs.filter(is_won=True)
        query = self.request.GET.get("q", "").strip()
        if query:
            qs = qs.filter(Q(name__icontains=query) | Q(account__name__icontains=query) | Q(external_id__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            query=self.request.GET.get("q", ""),
            won_only=self.request.GET.get("won") == "1",
            sync_state=SyncState.objects.filter(system=ExternalSystem.OPLACRM, entity="opportunities")
            .select_related("last_run")
            .first(),
        )
        return context
