from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("sales/opportunities/", views.OpportunityListView.as_view(), name="opportunity_list"),
]
