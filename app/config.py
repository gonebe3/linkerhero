from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from dotenv import load_dotenv, find_dotenv

# Load .env file robustly (project root)
_dot_env = find_dotenv()
if _dot_env:
    # Never override process environment variables (tests / deployments rely on env)
    load_dotenv(_dot_env, override=False)
else:
    load_dotenv(override=False)


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
    elif s.startswith("postgres://"):
        # Common alias used by some providers; map to SQLAlchemy psycopg3 dialect
        s = "postgresql+psycopg://" + s[len("postgres://"):]
    
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
    # Robust connection pooling for cloud Postgres (e.g., Neon) to avoid stale connections
    SQLALCHEMY_ENGINE_OPTIONS: dict[str, Any] = field(
        default_factory=lambda: {
            "pool_pre_ping": True,
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "300")),
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
        }
    )

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
    # Concrete model IDs (env-overridable to avoid hardcoding provider naming changes)
    # UI labels:
    # - ChatGPT 5.2 (OpenAI)
    # - Claude Sonnet 4.5 (Anthropic)
    OPENAI_MODEL_CHATGPT_5_2: str = os.getenv("OPENAI_MODEL_CHATGPT_5_2", "gpt-5")
    ANTHROPIC_MODEL_SONNET_4_5: str = os.getenv("ANTHROPIC_MODEL_SONNET_4_5", "claude-3-7-sonnet-20250219")

    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:5000")

    # Stripe
    STRIPE_PUBLISHABLE_KEY: str | None = os.getenv("STRIPE_PUBLISHABLE_KEY")
    STRIPE_SECRET_KEY: str | None = os.getenv("STRIPE_SECRET_KEY")

    # Ensure templates update without full restart in dev
    TEMPLATES_AUTO_RELOAD: bool = True

    # OCR settings (server-side)
    ENABLE_OCR: bool = os.getenv("ENABLE_OCR", "true").lower() in {"1", "true", "yes"}
    # Optional explicit path to tesseract binary (e.g., C:\\Program Files\\Tesseract-OCR\\tesseract.exe)
    TESSERACT_CMD: str | None = os.getenv("TESSERACT_CMD")
    # Optional path to poppler bin directory for pdf2image on Windows
    POPPLER_PATH: str | None = os.getenv("POPPLER_PATH")

    # PDF Vision extraction tuning
    PDF_VISION_MAX_PAGES: int = int(os.getenv("PDF_VISION_MAX_PAGES", "6"))
    PDF_VISION_SCALE: float = float(os.getenv("PDF_VISION_SCALE", "1.5"))
    PDF_VISION_TIMEOUT: float = float(os.getenv("PDF_VISION_TIMEOUT", "45.0"))
    PDF_VISION_PAGES_PER_BATCH: int = int(os.getenv("PDF_VISION_PAGES_PER_BATCH", "4"))
    PDF_VISION_MAX_WORKERS: int = int(os.getenv("PDF_VISION_MAX_WORKERS", "3"))

    # EasyOCR settings (default path for PDFs)
    PDF_EXTRACTOR: str = os.getenv("PDF_EXTRACTOR", "easyocr")  # easyocr | vision
    EASYOCR_LANGS: str = os.getenv("EASYOCR_LANGS", "en,lt")
    PDF_OCR_MAX_PAGES: int = int(os.getenv("PDF_OCR_MAX_PAGES", "15"))
    PDF_OCR_RENDER_SCALE: float = float(os.getenv("PDF_OCR_RENDER_SCALE", "1.5"))
    PDF_OCR_TIMEOUT_PER_PAGE: float = float(os.getenv("PDF_OCR_TIMEOUT_PER_PAGE", "8.0"))

    # OAuth - LinkedIn
    LINKEDIN_CLIENT_ID: str | None = os.getenv("LINKEDIN_CLIENT_ID")
    LINKEDIN_CLIENT_SECRET: str | None = os.getenv("LINKEDIN_CLIENT_SECRET")
    LINKEDIN_SCOPES: str = os.getenv("LINKEDIN_SCOPES", "openid profile email")

    # OAuth - Google
    GOOGLE_CLIENT_ID: str | None = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_SCOPES: str = os.getenv("GOOGLE_SCOPES", "openid email profile")

    # Article extraction (URL -> full content text) tuning
    ARTICLE_EXTRACT_TIMEOUT_S: float = float(os.getenv("ARTICLE_EXTRACT_TIMEOUT_S", "15.0"))
    ARTICLE_EXTRACT_MAX_BYTES: int = int(os.getenv("ARTICLE_EXTRACT_MAX_BYTES", str(2 * 1024 * 1024)))  # 2MB
    ARTICLE_EXTRACT_MAX_CHARS: int = int(os.getenv("ARTICLE_EXTRACT_MAX_CHARS", "20000"))
    ARTICLE_EXTRACT_MIN_CHARS: int = int(os.getenv("ARTICLE_EXTRACT_MIN_CHARS", "600"))
    ARTICLE_CONTENT_TTL_HOURS: int = int(os.getenv("ARTICLE_CONTENT_TTL_HOURS", "168"))  # 7 days

    # OAuth account linking behavior:
    # - true (default): if an existing user has the same email, OAuth will sign into that user (merged account).
    # - false: OAuth will only sign into a user if oauth_provider+oauth_sub match; if email already exists under a
    #          different auth method/provider, we refuse the login and ask the user to use the original method.
    OAUTH_LINK_BY_EMAIL: bool = os.getenv("OAUTH_LINK_BY_EMAIL", "true").lower() in {"1", "true", "yes"}

    # Celery configuration (for background tasks)
    CELERY_BROKER_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

