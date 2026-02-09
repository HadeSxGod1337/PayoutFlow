.PHONY: install migrate run worker test lint format shell createsuperuser test-cov requirements pre-commit pre-commit-install

# Требуется poetry в PATH (см. README)

install:
	poetry install

# Pre-commit: установить хуки в .git (один раз после clone)
pre-commit-install:
	poetry run pre-commit install

# Pre-commit: запустить все проверки по всему коду (для CI и локальной проверки)
pre-commit:
	poetry run pre-commit run --all-files

# Regenerate requirements.txt from Poetry (pinned versions for Docker). Requires poetry-plugin-export.
requirements:
	poetry export -f requirements.txt -o requirements.txt --without-hash --only main

migrate:
	poetry run python manage.py migrate

run:
	poetry run python manage.py runserver

worker:
	poetry run celery -A config worker -l info

test:
	poetry run pytest

test-cov:
	poetry run pytest --cov=config --cov=payouts --cov-report=term-missing

lint:
	poetry run ruff check config payouts tests
	poetry run mypy config payouts
	poetry run bandit -r config payouts -x payouts/migrations

format:
	poetry run ruff format config payouts tests
	poetry run ruff check --fix config payouts tests

shell:
	poetry run python manage.py shell

createsuperuser:
	poetry run python manage.py createsuperuser
