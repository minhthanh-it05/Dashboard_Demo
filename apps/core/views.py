import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health(request):
    """Unauthenticated liveness check; reports only whether the DB answers."""
    try:
        connection.ensure_connection()
    except Exception:
        logger.exception("Health check: database unavailable")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})
