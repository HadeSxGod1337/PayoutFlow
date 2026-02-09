from django.db import connection
from django.http import HttpRequest, JsonResponse


def health_check(request: HttpRequest) -> JsonResponse:
    try:
        connection.ensure_connection()
    except Exception:
        return JsonResponse({"status": "unhealthy"}, status=503)
    return JsonResponse({"status": "healthy"})
