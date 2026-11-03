from django.urls import path

from . import views

app_name = "procurement"

P = "projects/<uuid:project_pk>/purchases"

urlpatterns = [
    path(f"{P}/new/", views.PurchaseRequestCreateView.as_view(), name="create"),
    path(f"{P}/<int:pk>/", views.PurchaseRequestDetailView.as_view(), name="detail"),
    path(f"{P}/<int:pk>/edit/", views.PurchaseRequestUpdateView.as_view(), name="update"),
    path(f"{P}/<int:pk>/items/new/", views.PurchaseItemCreateView.as_view(), name="item_create"),
    path(f"{P}/<int:pk>/status/new/", views.PurchaseStatusCreateView.as_view(), name="status_create"),
]
