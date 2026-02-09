# Развёртывание PayoutFlow на сервере

Пошаговая инструкция по запуску проекта на сервере: с Docker (рекомендуется) и без Docker (systemd + Nginx).

---

## Вариант A: Сервер с Docker и Docker Compose

Подходит для VPS (Ubuntu/Debian или облачный инстанс) с установленным Docker.

### 1. Подготовка сервера

**Ubuntu/Debian — установка Docker и Docker Compose:**

```bash
# Установка Docker (официальный скрипт)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Выйти и зайти снова, чтобы применилась группа

# Docker Compose (v2 входит в пакет docker-compose-plugin)
sudo apt-get update
sudo apt-get install -y docker-compose-plugin
docker compose version
```

Опционально: создать отдельного пользователя для приложения и работать не под root.

### 2. Код и конфигурация

```bash
git clone <URL-репозитория> PayoutFlow
cd PayoutFlow
cp .env.example .env
```

Отредактировать `.env` и задать **production**-значения:

- `DEBUG=False`
- `SECRET_KEY=<сгенерированный секрет>` (например, `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
- `ALLOWED_HOSTS=your-domain.com,api.your-domain.com` (или IP сервера)
- `POSTGRES_PASSWORD=<надёжный пароль>`
- `DATABASE_URL=postgres://payoutflow:<тот же пароль>@db:5432/payoutflow`
- `CELERY_BROKER_URL=redis://redis:6379/0`
- `DJANGO_SETTINGS_MODULE=config.settings.production`

### 3. Запуск

```bash
docker compose up -d --build
```

Проверка с сервера:

```bash
curl http://localhost:8000/api/health/
# Ожидается: {"status":"healthy","database":"ok","redis":"ok"}
```

### 4. Доступ снаружи и HTTPS

Порт 8000 не должен быть открыт в интернет. Перед приложением нужен **обратный прокси** с TLS.

**Пример Nginx** (Ubuntu: `sudo apt install nginx`, сайт в `/etc/nginx/sites-available/payoutflow`):

```nginx
server {
    listen 80;
    server_name api.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name api.your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/api.your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Сертификаты Let's Encrypt (certbot):

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.your-domain.com
```

Включить сайт и перезагрузить nginx:

```bash
sudo ln -s /etc/nginx/sites-available/payoutflow /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5. Обновление

```bash
cd PayoutFlow
git pull
# При необходимости обновить .env
docker compose up -d --build
```

Миграции выполняются при старте контейнера `web`.

---

## Вариант B: Сервер без Docker (systemd + Poetry/venv)

Для установки PostgreSQL, Redis и приложения вручную на уже существующий сервер.

### 1. ОС и сервисы

**Ubuntu 22.04 (пример):**

```bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip postgresql-14 redis-server nginx
# Poetry
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

**PostgreSQL — создать БД и пользователя:**

```bash
sudo -u postgres psql -c "CREATE USER payoutflow WITH PASSWORD 'ваш_пароль';"
sudo -u postgres psql -c "CREATE DATABASE payoutflow OWNER payoutflow;"
```

**Redis** обычно уже запущен: `sudo systemctl status redis-server`.

### 2. Приложение

```bash
cd /opt  # или выбранная директория
sudo git clone <URL-репозитория> PayoutFlow
sudo chown -R $USER:$USER PayoutFlow
cd PayoutFlow

poetry config virtualenvs.in-project true
poetry install --no-dev

cp .env.example .env
# Отредактировать .env: DATABASE_URL=postgres://payoutflow:ваш_пароль@localhost:5432/payoutflow,
# CELERY_BROKER_URL=redis://localhost:6379/0, SECRET_KEY, ALLOWED_HOSTS, DEBUG=False

export DJANGO_SETTINGS_MODULE=config.settings.production
poetry run python manage.py migrate --noinput
poetry run python manage.py collectstatic --noinput
```

### 3. Systemd — юниты

Пусть приложение лежит в `/opt/PayoutFlow`, виртуальное окружение — `/opt/PayoutFlow/.venv`.

**`/etc/systemd/system/payoutflow-gunicorn.service`:**

```ini
[Unit]
Description=PayoutFlow Gunicorn
After=network.target postgresql.service redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/PayoutFlow
Environment="PATH=/opt/PayoutFlow/.venv/bin"
EnvironmentFile=/opt/PayoutFlow/.env
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
ExecStart=/opt/PayoutFlow/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 4 --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/payoutflow-celery-worker.service`:**

```ini
[Unit]
Description=PayoutFlow Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/PayoutFlow
Environment="PATH=/opt/PayoutFlow/.venv/bin"
EnvironmentFile=/opt/PayoutFlow/.env
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
ExecStart=/opt/PayoutFlow/.venv/bin/celery -A config worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/payoutflow-celery-beat.service`:**

```ini
[Unit]
Description=PayoutFlow Celery Beat
After=network.target postgresql.service redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/PayoutFlow
Environment="PATH=/opt/PayoutFlow/.venv/bin"
EnvironmentFile=/opt/PayoutFlow/.env
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
ExecStart=/opt/PayoutFlow/.venv/bin/celery -A config beat -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

Права и запуск:

```bash
sudo chown -R www-data:www-data /opt/PayoutFlow
sudo systemctl daemon-reload
sudo systemctl enable payoutflow-gunicorn payoutflow-celery-worker payoutflow-celery-beat
sudo systemctl start payoutflow-gunicorn payoutflow-celery-worker payoutflow-celery-beat
sudo systemctl status payoutflow-gunicorn payoutflow-celery-worker payoutflow-celery-beat
```

### 4. Nginx с SSL

Аналогично варианту A: виртуальный хост с `proxy_pass http://127.0.0.1:8000` и заголовками `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`, плюс SSL (certbot). Файл сайта в `/etc/nginx/sites-available/payoutflow` — конфиг из варианта A подходит без изменений.

### 5. Health check

Для мониторинга или скриптов можно вызывать с сервера:

```bash
curl -f http://127.0.0.1:8000/api/health/
```

---

## Итог

- **Вариант A:** Docker + Docker Compose → `.env` для прода → `docker compose up -d --build` → Nginx + SSL.
- **Вариант B:** PostgreSQL + Redis + Nginx → код + Poetry + `.env` → migrate + collectstatic → systemd (gunicorn, worker, beat) → Nginx + SSL.

В обоих случаях для доступа из интернета обязательны обратный прокси и HTTPS.
