from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def normalize_neon_url(url: str | None) -> str | None:
    """Clean up Neon URLs from .env that might have psql wrapper or quotes"""
    if not url:
        return None
    
    s = url.strip()
    
    # Remove psql command wrapper if present
    if s.lower().startswith("psql "):
        s = s[5:].strip()
    
    # Remove surrounding quotes if present
    if s.startswith("'") and s.endswith("'"):
        s = s[1:-1]
    elif s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    
    # Convert to psycopg3 format
    if s.startswith("postgresql://"):
        s = "postgresql+psycopg://" + s[len("postgresql://"):]
    
    return s


@dataclass
class Config:
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret")

    # Database URLs - prioritize your .env variable names
    _db_runtime = normalize_neon_url(os.getenv("DATABASE_URL"))
    _db_direct = normalize_neon_url(os.getenv("DATABASE_URL_DIRECT"))
    
    SQLALCHEMY_DATABASE_URI: str = _db_runtime or "sqlite+pysqlite:///linkerhero.sqlite3"
    SQLALCHEMY_DATABASE_URI_DIRECT: str = _db_direct or _db_runtime or "sqlite+pysqlite:///linkerhero.sqlite3"

    SESSION_COOKIE_SECURE: bool = FLASK_ENV == "production"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # Email settings - support your Gmail setup
    MAIL_FROM: str | None = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_FROM")
    SMTP_HOST: str | None = os.getenv("MAIL_SERVER") or os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("MAIL_PORT") or os.getenv("SMTP_PORT") or "587")
    SMTP_USER: str | None = os.getenv("MAIL_USERNAME") or os.getenv("SMTP_USER")
    SMTP_PASS: str | None = os.getenv("MAIL_PASSWORD") or os.getenv("SMTP_PASS")

    # LLM settings
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:5000")

