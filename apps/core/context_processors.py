from django.conf import settings

from .navigation import current_section


def demo_mode(request):
    return {"DEMO_MODE": settings.DEMO_MODE}


def navigation(request):
    return {"nav_section": current_section(request)}
