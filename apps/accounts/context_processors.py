from .roles import (
    can_import_finance,
    can_manage_integrations,
    can_view_finance,
    can_view_handovers,
    can_view_integrations,
    can_view_sales_data,
    is_project_manager,
)


def roles(request):
    user = getattr(request, "user", None)
    if user is None:
        return {}
    return {
        "is_pm": is_project_manager(user),
        "can_view_finance": can_view_finance(user),
        "can_view_handovers": can_view_handovers(user),
        "can_view_sales_data": can_view_sales_data(user),
        "can_view_integrations": can_view_integrations(user),
        "can_manage_integrations": can_manage_integrations(user),
        "can_import_finance": can_import_finance(user),
    }
