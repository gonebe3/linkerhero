PY ?= python
PIP ?= pip

.PHONY: setup run fmt lint test migrate revision seed alembic-init precommit-install

setup:
	$(PIP) install -r requirements.txt
	pre-commit install

run:
	$(PY) -m flask --app app run --debug

fmt:
	black .
	ruff check . --fix

lint:
	ruff check .
	mypy app

test:
	pytest

alembic-init:
	$(PY) -m alembic init migrations

revision:
	$(PY) -m alembic revision --autogenerate -m "init"

migrate:
	$(PY) -m alembic upgrade head

seed:
	$(PY) -m flask --app app rss:refresh

