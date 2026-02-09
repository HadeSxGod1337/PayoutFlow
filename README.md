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
| `make shell` | Django shell |
| `make createsuperuser` | Создание суперпользователя |

---

## API

- **Заявки:** `GET/POST /api/payouts/`, `GET/PATCH/DELETE /api/payouts/{id}/`
- **Проверка состояния (health):** `GET /api/health/` — доступность БД; при ошибке возвращается 503 и `{"status": "unhealthy"}`.
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

Допустимые валюты: `RUB`, `USD`, `EUR`, `GBP`, `KZT`. `amount` — строка с числом, больше 0. `recipient_details` — любой непустой JSON-объект (до 2000 символов в сериализованном виде).

**GET /api/payouts/** — фильтр по статусу: добавьте query-параметр `status` со значением `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED` или `CANCELLED`.

**PATCH /api/payouts/{id}/** — отмена заявки (только для статусов PENDING или PROCESSING):

```json
{
  "status": "CANCELLED"
}
```

Через API можно только перевести заявку в `CANCELLED`; статусы `COMPLETED` и `FAILED` выставляет система.

---

## Деплой

### Необходимые сервисы

- **Приложение:** Django под gunicorn (не dev-сервер).
- **Воркер:** Celery worker для фоновой обработки заявок.
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

Для деплоя в режиме production задайте в `.env`: `DJANGO_SETTINGS_MODULE=config.settings.production`.

Health check для контейнера `web`: запрос к `GET /api/health/`.

### CI

GitHub Actions (`.github/workflows/ci.yml`) — тесты и линтеры.
