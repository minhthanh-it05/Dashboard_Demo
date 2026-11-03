from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("finance/", views.FinanceOverviewView.as_view(), name="overview"),
    path("finance/import/", views.FinanceCsvImportView.as_view(), name="import"),
    path("finance/batches/<int:pk>/", views.FinanceBatchDetailView.as_view(), name="batch_detail"),
]
