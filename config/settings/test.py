import copy

from config.settings.base import *  # noqa: F401, F403
from config.settings.base import LOGGING

DEBUG = True
SECRET_KEY = "test-secret-key"  # nosec B105 - test-only settings
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Reduce log noise during tests; base config remains single source of truth
LOGGING = copy.deepcopy(LOGGING)
LOGGING["loggers"]["payouts"]["level"] = "WARNING"  # type: ignore[index]
