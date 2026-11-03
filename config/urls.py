from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("accounts/", include("apps.accounts.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.procurement.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.integrations.urls")),
    path("", include("apps.sales.urls")),
    path("", include("apps.finance.urls")),
    path("", include("apps.dashboard.urls")),
]
