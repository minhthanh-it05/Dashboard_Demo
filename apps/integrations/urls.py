from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("integrations/", views.IntegrationStatusView.as_view(), name="status"),
    path("integrations/run/<slug:key>/", views.RunSyncJobView.as_view(), name="run"),
]
