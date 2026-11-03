from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.PMDashboardView.as_view(), name="pm"),
    path("my-work/", views.MyWorkView.as_view(), name="my_work"),
]
