from django.conf import settings
from django.db import connection
from django.http import HttpRequest, JsonResponse


def _check_redis() -> bool:
    """Return True if Redis (Celery broker) is reachable."""
    try:
        import redis

        client = redis.from_url(settings.CELERY_BROKER_URL)  # type: ignore[no-untyped-call]
        client.ping()
        return True
    except Exception:
        return False


def health_check(request: HttpRequest) -> JsonResponse:
    checks: dict[str, str] = {}
    db_ok = False
    try:
        connection.ensure_connection()
        db_ok = True
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    redis_ok = _check_redis()
    checks["redis"] = "ok" if redis_ok else "unavailable"

    if db_ok and redis_ok:
        return JsonResponse({"status": "healthy", **checks})
    return JsonResponse({"status": "unhealthy", "checks": checks}, status=503)
