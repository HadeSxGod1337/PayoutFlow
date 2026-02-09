from celery import Celery  # type: ignore[import-untyped]

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
