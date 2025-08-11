from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass
class Config:
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret")

    # Accept multiple env naming styles
    _db_runtime = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    _db_direct = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DB_URL_DIRECT")
    # Normalize accidental inclusion of `psql '...'` wrapper
    def _strip_psql(s: str | None) -> str | None:
        if not s:
            return s
        s = s.strip()
        if s.lower().startswith("psql "):
            s = s[5:].strip()
        if s.startswith("'") and s.endswith("'"):
            s = s[1:-1]
        return s

    def _rewrite_driver(s: str | None) -> str | None:
        if not s:
            return s
        if s.startswith("postgresql://"):
            return "postgresql+psycopg://" + s[len("postgresql://") :]
        return s

    _db_runtime = _rewrite_driver(_strip_psql(_db_runtime))
    _db_direct = _rewrite_driver(_strip_psql(_db_direct))

    SQLALCHEMY_DATABASE_URI: str = _db_runtime or "sqlite+pysqlite:///linkerhero.sqlite3"
    SQLALCHEMY_DATABASE_URI_DIRECT: str = _db_direct or _db_runtime or "sqlite+pysqlite:///linkerhero.sqlite3"

    SESSION_COOKIE_SECURE: bool = FLASK_ENV == "production"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # Support both custom and Flask-Mail-like keys
    MAIL_FROM: str | None = os.getenv("MAIL_FROM") or os.getenv("MAIL_DEFAULT_SENDER")
    SMTP_HOST: str | None = os.getenv("SMTP_HOST") or os.getenv("MAIL_SERVER")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT") or os.getenv("MAIL_PORT") or "587")
    SMTP_USER: str | None = os.getenv("SMTP_USER") or os.getenv("MAIL_USERNAME")
    SMTP_PASS: str | None = os.getenv("SMTP_PASS") or os.getenv("MAIL_PASSWORD")

    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:5000")

