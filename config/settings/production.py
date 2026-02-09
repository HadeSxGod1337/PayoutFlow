from config.settings.base import *  # noqa: F401, F403

DEBUG = False

if SECRET_KEY == "change-me-in-production":  # nosec B105
    raise RuntimeError(
        "Set SECRET_KEY in production (e.g. in .env). Do not use the default."
    )

# Security: HTTPS and cookies
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
