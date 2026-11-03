from django.urls import path

from . import handover_views, views

app_name = "projects"

P = "projects/<uuid:project_pk>"

urlpatterns = [
    path("projects/", views.ProjectListView.as_view(), name="list"),
    path("projects/new/", views.ProjectCreateView.as_view(), name="create"),
    path("projects/<uuid:pk>/", views.ProjectDetailView.as_view(), name="detail"),
    path("projects/<uuid:pk>/edit/", views.ProjectUpdateView.as_view(), name="update"),
    path(f"{P}/members/add/", views.MemberAddView.as_view(), name="member_add"),
    path(f"{P}/members/<int:pk>/remove/", views.MemberRemoveView.as_view(), name="member_remove"),
    path(f"{P}/milestones/new/", views.MilestoneCreateView.as_view(), name="milestone_create"),
    path(f"{P}/milestones/<int:pk>/edit/", views.MilestoneUpdateView.as_view(), name="milestone_update"),
    path(f"{P}/tasks/new/", views.TaskCreateView.as_view(), name="task_create"),
    path(f"{P}/tasks/<int:pk>/edit/", views.TaskUpdateView.as_view(), name="task_update"),
    path(f"{P}/tasks/<int:pk>/status/", views.TaskStatusView.as_view(), name="task_status"),
    path(f"{P}/progress/new/", views.ProgressUpdateCreateView.as_view(), name="progress_create"),
    path(f"{P}/issues/new/", views.IssueCreateView.as_view(), name="issue_create"),
    path(f"{P}/issues/<int:pk>/edit/", views.IssueUpdateView.as_view(), name="issue_update"),
    path(f"{P}/kickoffs/new/", views.KickoffCreateView.as_view(), name="kickoff_create"),
    path(f"{P}/kickoffs/<int:pk>/edit/", views.KickoffUpdateView.as_view(), name="kickoff_update"),
    path(f"{P}/contracts/new/", views.ContractCreateView.as_view(), name="contract_create"),
    path(f"{P}/contracts/<int:pk>/edit/", views.ContractUpdateView.as_view(), name="contract_update"),
    path(f"{P}/documents/new/", views.DocumentCreateView.as_view(), name="document_create"),
    path(f"{P}/documents/<int:pk>/edit/", views.DocumentUpdateView.as_view(), name="document_update"),
    # Sales handover
    path("handovers/", handover_views.HandoverListView.as_view(), name="handover_list"),
    path("handovers/new/", handover_views.HandoverCreateView.as_view(), name="handover_create"),
    path("handovers/<int:pk>/", handover_views.HandoverDetailView.as_view(), name="handover_detail"),
    path("handovers/<int:pk>/edit/", handover_views.HandoverUpdateView.as_view(), name="handover_update"),
    path("handovers/<int:pk>/review/", handover_views.HandoverReviewView.as_view(), name="handover_review"),
    path(
        "handovers/<int:pk>/create-project/",
        handover_views.HandoverCreateProjectView.as_view(),
        name="handover_create_project",
    ),
]
