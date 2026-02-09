# PayoutFlow

REST API для управления заявками на выплату. Django, DRF, Celery, PostgreSQL.

## Требования

- Python 3.10+
- [Poetry](https://python-poetry.org/) (установка: `pip install poetry` или [официальный установщик](https://python-poetry.org/docs/#installation))
- PostgreSQL
- Redis

---

## Инструкция по запуску

### 1. Установка зависимостей

Создайте виртуальное окружение и установите зависимости через Poetry:

```bash
poetry config virtualenvs.in-project true
poetry install
```

(Опционально: `poetry shell` — активировать окружение. Команды ниже можно выполнять и через `make`, тогда активация не нужна.)

### 2. Переменные окружения

Скопируйте пример и задайте параметры БД и брокера:

```bash
cp .env.example .env
```

В `.env` укажите `SECRET_KEY`, `DATABASE_URL` (PostgreSQL), `CELERY_BROKER_URL` (Redis).

### 3. Запуск миграций

```bash
make migrate
```

### 4. Запуск приложения

```bash
make run
```

API будет доступен по адресу http://localhost:8000/api/

### 5. Запуск Celery worker

В отдельном терминале:

```bash
make worker
```

### 5.1. Запуск Celery beat (опционально, для продакшена)

Для автоматического перевода «застрявших» заявок (PROCESSING дольше N минут) в FAILED запустите beat:

```bash
celery -A config beat -l info
```

### 6. Запуск тестов

```bash
make test
```

---

## Makefile

Базовые команды:

| Команда | Описание |
|--------|----------|
| `make run` | Запуск сервиса (Django dev-сервер) |
| `make test` | Запуск тестов |
| `make worker` | Запуск Celery worker |
| `make migrate` | Применение миграций |

Дополнительно:

| Команда | Описание |
|--------|----------|
| `make install` | Установка зависимостей (poetry install) |
| `make test-cov` | Тесты с отчётом покрытия |
| `make lint` | Проверка кода (ruff, mypy, bandit) |
| `make format` | Форматирование кода (ruff) |
| `make pre-commit-install` | Установить pre-commit хуки в репозиторий (один раз) |
| `make pre-commit` | Запустить все pre-commit проверки по всему коду |
| `make shell` | Django shell |
| `make createsuperuser` | Создание суперпользователя |

После `make pre-commit-install` при каждом `git commit` автоматически запускаются ruff, mypy, bandit и базовые проверки (пробелы, YAML и т.д.).

---

## API

- **Заявки:** `GET/POST /api/payouts/`, `GET/PATCH/DELETE /api/payouts/{id}/`
- **Проверка состояния (health):** `GET /api/health/` — проверка БД и Redis (очередь Celery); при успехе — 200 и `{"status": "healthy", "database": "ok", "redis": "ok"}`, при ошибке — 503 и `{"status": "unhealthy", "checks": {...}}`.
- **Документация (OpenAPI):** `/api/schema/`, **Swagger UI:** http://localhost:8000/api/docs/, **ReDoc:** http://localhost:8000/api/redoc/

### Тестовые данные для Swagger (ручная проверка)

Скопируйте JSON ниже в тело запроса в Swagger UI.

**POST /api/payouts/** — создание заявки (минимальный пример):

```json
{
  "amount": "100.50",
  "currency": "USD",
  "recipient_details": {
    "account": "12345678",
    "bank": "Test Bank",
    "name": "Иван Иванов"
  }
}
```

**POST /api/payouts/** — с описанием и другой валютой:

```json
{
  "amount": "5000.00",
  "currency": "RUB",
  "recipient_details": {
    "card": "4276********1234",
    "phone": "+79001234567",
    "name": "Получатель"
  },
  "description": "Выплата по договору №123"
}
```

Допустимые валюты: `RUB`, `USD`, `EUR`, `GBP`, `KZT`. `amount` — строка с числом, больше 0. `recipient_details` — любой непустой JSON-объект (до 2000 символов в сериализованном виде). Для идемпотентности при повторных запросах передайте заголовок `Idempotency-Key` (например, UUID).

**GET /api/payouts/** — фильтр по статусу: добавьте query-параметр `status` со значением `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED` или `CANCELLED`.

**PATCH /api/payouts/{id}/** — отмена заявки (только для статусов PENDING или PROCESSING):

```json
{
  "status": "CANCELLED"
}
```

Через API можно только перевести заявку в `CANCELLED`; статусы `COMPLETED` и `FAILED` выставляет система.

**Идемпотентность создания:** при повторном запросе с тем же телом и заголовком `Idempotency-Key` (например, UUID) возвращается ранее созданная заявка с кодом 200. Разный тело при том же ключе — 422.

**DELETE:** удаление разрешено только для заявок в статусах PENDING, PROCESSING, CANCELLED. Удаление COMPLETED/FAILED запрещено (аудит и соответствие требованиям).

### Безопасность и аутентификация

По умолчанию API не требует аутентификации (тестовый режим). **Перед выкладкой в прод или в контур, похожий на прод, необходимо:**

- Включить аутентификацию в DRF: задать `DEFAULT_AUTHENTICATION_CLASSES` (например, `rest_framework.authentication.TokenAuthentication` или JWT) и `DEFAULT_PERMISSION_CLASSES` (например, `IsAuthenticated`) в настройках.
- Ограничить доступ по ролям при необходимости (только определённые пользователи/сервисы могут создавать выплаты или отменять их).
- Использовать HTTPS и переменные окружения для секретов (см. раздел «Деплой»).

---

## Деплой

### Необходимые сервисы

- **Приложение:** Django под gunicorn (не dev-сервер).
- **Воркер:** Celery worker для фоновой обработки заявок.
- **Beat (рекомендуется):** Celery beat для периодической задачи восстановления застрявших заявок (PROCESSING → FAILED).
- **БД:** PostgreSQL.
- **Брокер:** Redis (очередь задач Celery).

### Переменные окружения (production)

- `DEBUG=False`
- `SECRET_KEY` — уникальный секрет (не использовать значение по умолчанию).
- `ALLOWED_HOSTS` — через запятую домены/хосты (например, `api.example.com`).
- `DATABASE_URL` — строка подключения PostgreSQL.
- `CELERY_BROKER_URL` — URL Redis.

Используйте настройки **production:** `DJANGO_SETTINGS_MODULE=config.settings.production`. В Docker по умолчанию — development (для локальной проверки); для прода задайте эту переменную в `.env`.

### Шаги на сервере

1. Установить зависимости, скопировать `.env` из `.env.example` и заполнить значения для прода.
2. **Миграции:** `python manage.py migrate --noinput`
3. **Статика (если отдаётся приложением):** `python manage.py collectstatic --noinput`
4. **Запуск приложения:** например, `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4` (workers/threads — по нагрузке).
5. **Запуск Celery:** в отдельном процессе `celery -A config worker -l info` (через systemd/supervisor или аналог).
6. Оркестрация и проверка жизни: использовать эндпоинт `GET /api/health/` для health check (Docker, k8s, балансировщики).

### Docker Compose

`cp .env.example .env`, задать `POSTGRES_PASSWORD` и при необходимости другие переменные, затем:

```bash
docker compose up --build
```

По умолчанию используется **development** (http://localhost:8000, без редиректа на https). API: http://localhost:8000/api/health/ и т.д.

Для деплоя в режиме production задайте в `.env`: `DJANGO_SETTINGS_MODULE=config.settings.production`. При `docker compose up` поднимаются сервисы **web**, **worker** и **beat** (восстановление застрявших заявок). Для контейнера `web` в Compose настроен **healthcheck** по `GET /api/health/` — оркестраторы могут использовать его для перезапуска нездорового контейнера.

Для воспроизводимой сборки образа можно заранее сгенерировать зафиксированные версии зависимостей: `make requirements` (экспорт из Poetry в `requirements.txt`).

### Запуск на сервере от и до

**Доступ из интернета:** порт приложения (8000) не должен быть открыт наружу напрямую. Перед приложением нужен **обратный прокси** (nginx, Caddy, Traefik) с **HTTPS** (например, Let's Encrypt). Production-настройки уже учитывают прокси (`SECURE_PROXY_SSL_HEADER`).

- **Вариант A — Docker Compose (рекомендуется):** установить Docker и Docker Compose на сервер → клонировать репозиторий → скопировать `.env.example` в `.env` и задать production-значения (`DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `DJANGO_SETTINGS_MODULE=config.settings.production`, пароль БД и т.д.) → выполнить `docker compose up -d --build` → настроить nginx (или аналог) с SSL и `proxy_pass` на `http://127.0.0.1:8000` с заголовком `X-Forwarded-Proto: $scheme`.
- **Вариант B — без Docker (systemd):** установить Python 3.10+, PostgreSQL, Redis, Nginx → клонировать репозиторий, `poetry install --no-dev`, настроить `.env` для прода → `migrate` и `collectstatic` → запустить через systemd: gunicorn (порт 127.0.0.1:8000), Celery worker, Celery beat → настроить Nginx с SSL и проксированием на приложение.

Подробные шаги (команды установки, примеры systemd-юнитов и конфиг nginx) — в [docs/DEPLOY.md](docs/DEPLOY.md).

### CI

GitHub Actions (`.github/workflows/ci.yml`) — тесты и линтеры.
