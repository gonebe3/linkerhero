# LinkerHero

Production-ready Flask + HTMX app with Postgres (Railway/Neon), Alembic, and LLM provider routing (Anthropic/OpenAI).

## Setup

1. Create a virtualenv and install deps:

```
python -m venv .venv && . .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Copy env:

```
cp .env.example .env  # On Windows: copy .env.example .env
```

Fill secrets locally. Do not commit.

## Environment

- FLASK_ENV: development|production
- SECRET_KEY
- DATABASE_URL: Postgres runtime URL (Railway/Neon)
- DATABASE_URL_DIRECT: Postgres direct URL for Alembic migrations (optional; falls back to DATABASE_URL)
- MAIL_FROM, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
- LLM_PROVIDER: anthropic|openai
- ANTHROPIC_API_KEY, OPENAI_API_KEY
- APP_BASE_URL
- REDIS_URL (for rate limiting; memory:// used if unset in dev)

Notes:
- We normalize both `postgresql://` and `postgres://` to `postgresql+psycopg://` automatically.
- In production, include `sslmode=require` if your provider needs it.

## Local run

```
make setup
make migrate
make run
```

Home: `/` • News: `/news` • Generate: `/generate` • Login: `/login`

## Migrations

```
make revision  # autogenerate new migration
make migrate   # upgrade to head
```

Alembic uses `DATABASE_URL_DIRECT` if set, otherwise `DATABASE_URL`.

## Migrations (direct CLI; Flask-SQLAlchemy + Alembic)

Windows PowerShell examples:

```
# Ensure venv is active
. .venv\Scripts\Activate.ps1

# Create revision from current models
python -m flask --app app:create_app db revision -m "sync models" --autogenerate

# Apply migrations to DB (uses SQLALCHEMY_DATABASE_URI from .env)
python -m flask --app app:create_app db upgrade
```

Notes:
- Models live in `app/models.py` and use `db.Model` (Flask-SQLAlchemy).
- Alembic reads metadata from Flask-SQLAlchemy and the database URL from app config.
- `.env` should include: `FLASK_APP=app:create_app`, `FLASK_ENV`, `DATABASE_URL` and optionally `DATABASE_URL_DIRECT`.

## CLI

- rss:refresh — ingest feeds now
- db:ping — SELECT 1
- user:create_admin EMAIL — bootstrap admin

Run via:

```
python -m flask --app app rss:refresh
```

## Deploy

- Use `Procfile` with Gunicorn: `web: gunicorn 'app:create_app()' --workers 2 --threads 4 --timeout 60`
- Set env vars in your host (Railway/Render/Fly/Heroku). Configure `APP_BASE_URL` to your prod URL.
- Add a scheduler/cron to call `rss:refresh` every 3–6h.

## Testing

```
pytest -q
```

## Git

```
git init
git add .
git commit -m "init: LinkerHero scaffold"
git branch -M main
git remote add origin YOUR_GIT_REMOTE
git push -u origin main
```

