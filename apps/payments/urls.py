from django.urls import path

from . import views

app_name = "payments"

P = "projects/<uuid:project_pk>/payments"

urlpatterns = [
    path(f"{P}/new/", views.PaymentRequestCreateView.as_view(), name="create"),
    path(f"{P}/<int:pk>/", views.PaymentRequestDetailView.as_view(), name="detail"),
    path(f"{P}/<int:pk>/edit/", views.PaymentRequestUpdateView.as_view(), name="update"),
    path(f"{P}/<int:pk>/status/new/", views.PaymentStatusCreateView.as_view(), name="status_create"),
]
