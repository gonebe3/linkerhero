from __future__ import annotations

from flask import Flask
import re
import os
from .config import Config
from .db import db, db_session
from sqlalchemy import text

from .main.routes import bp as main_bp
from .auth.routes import bp as auth_bp
from .news.routes import bp as news_bp
from .gen.routes import bp as gen_bp
from .billing import bp as billing_bp
from flask_wtf.csrf import CSRFProtect, CSRFError
from .limiter import limiter


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config())
    # Increase max upload size to 50 MB for file-based generation
    app.config.setdefault("MAX_CONTENT_LENGTH", 50 * 1024 * 1024)

    # SQLite doesn't support the same pooling options as Postgres; avoid passing them.
    try:
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if isinstance(uri, str) and uri.startswith("sqlite"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}
    except Exception:
        pass

    # Derive cookie security from APP_BASE_URL to avoid "secure cookie on http"
    # which breaks login persistence (common cause of OAuth not logging in).
    try:
        base = app.config.get("APP_BASE_URL", "")
        if isinstance(base, str) and base.startswith("https://"):
            app.config["SESSION_COOKIE_SECURE"] = True
        elif isinstance(base, str) and base.startswith("http://"):
            app.config["SESSION_COOKIE_SECURE"] = False
    except Exception:
        pass

    # Initialize Flask-SQLAlchemy
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)
    # Ensure models are imported so metadata is populated for Alembic autogenerate
    from . import models as _models  # noqa: F401

    # Initialize Flask-Alembic to provide `flask db` commands
    from flask_alembic import Alembic
    import click
    alembic = Alembic()
    alembic.init_app(app)

    # Provide familiar `flask db` commands that proxy to Alembic directly
    import os
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    def _alembic_cfg() -> AlembicConfig:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        ini_path = os.path.join(repo_root, "alembic.ini")
        cfg = AlembicConfig(ini_path)
        cfg.set_main_option("script_location", os.path.join(repo_root, "migrations"))
        # URL is taken from migrations/env.py via current_app; cfg url here is optional
        return cfg

    @app.cli.group('db')
    def db_cli():
        """Database migration commands (Alembic)."""
        pass

    @db_cli.command('revision')
    @click.option("--message", "-m", required=False, default="", help="Revision message")
    @click.option("--autogenerate", is_flag=True, default=True)
    def db_revision(message: str, autogenerate: bool) -> None:
        alembic_command.revision(_alembic_cfg(), message=message, autogenerate=autogenerate)

    @db_cli.command('upgrade')
    @click.argument("revision", required=False, default="head")
    def db_upgrade(revision: str) -> None:
        alembic_command.upgrade(_alembic_cfg(), revision)

    @db_cli.command('downgrade')
    @click.argument("revision", required=False, default="-1")
    def db_downgrade(revision: str) -> None:
        alembic_command.downgrade(_alembic_cfg(), revision)

    @db_cli.command('current')
    @click.option("--verbose", is_flag=True, default=False)
    def db_current(verbose: bool) -> None:
        alembic_command.current(_alembic_cfg(), verbose=verbose)

    @db_cli.command('heads')
    @click.option("--verbose", is_flag=True, default=False)
    def db_heads(verbose: bool) -> None:
        alembic_command.heads(_alembic_cfg(), verbose=verbose)

    @db_cli.command('history')
    @click.option("--verbose", is_flag=True, default=False)
    def db_history(verbose: bool) -> None:
        alembic_command.history(_alembic_cfg(), verbose=verbose)

    @db_cli.command('stamp')
    @click.argument("revision", required=False, default="head")
    def db_stamp(revision: str) -> None:
        alembic_command.stamp(_alembic_cfg(), revision)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(gen_bp)
    app.register_blueprint(billing_bp)

    # CSRF protection (global)
    csrf = CSRFProtect()
    csrf.init_app(app)

    # Rate limiting (global)
    limiter.init_app(app)

    # Exempt Stripe webhook (validated by Stripe signature separately)
    try:
        from .billing.routes import stripe_webhook as _stripe_webhook
        csrf.exempt(_stripe_webhook)
    except Exception:
        pass

    # Friendly CSRF error handler
    from flask import request, jsonify, render_template

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):  # type: ignore[override]
        try:
            if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
                return jsonify({"error": "CSRF token missing or invalid"}), 400
        except Exception:
            pass
        try:
            return render_template("billing_error.html", message="Security check failed. Please refresh and try again."), 400
        except Exception:
            return ("CSRF token missing or invalid", 400)

    # Friendly 429 handler
    @app.errorhandler(429)
    def handle_rate_limit(e):  # type: ignore[override]
        try:
            # Extract information if provided by limiter headers
            retry_after = None
            try:
                retry_after = int(request.headers.get('Retry-After', '0'))
            except Exception:
                retry_after = None
            return render_template(
                "rate_limited.html",
                title="Too Many Requests",
                message="You’ve hit a temporary rate limit. Please wait a moment and try again.",
                retry_after=retry_after,
            ), 429
        except Exception:
            return ("Too Many Requests", 429)

    @app.errorhandler(404)
    def handle_not_found(e):  # type: ignore[override]
        try:
            return render_template("errors/404.html"), 404
        except Exception:
            return ("Page not found", 404)

    @app.errorhandler(500)
    def handle_server_error(e):  # type: ignore[override]
        try:
            return render_template("errors/500.html"), 500
        except Exception:
            return ("Something went wrong", 500)

    # Session last_seen tracker
    from flask import request
    from .models import User, Session as UserSession
    from .db import db_session as _dbs
    from datetime import datetime, timezone

    @app.before_request
    def _update_last_seen():
        from flask import session as _flask_session
        uid = _flask_session.get("user_id")
        if not uid:
            return
        now = datetime.now(timezone.utc)
        with _dbs() as s:
            user = s.get(User, uid)
            if user:
                user.last_seen_at = now
                # Auto-renew monthly quotas if past renewal date
                try:
                    from .utils import next_month
                    if user.plan_renews_at and now >= user.plan_renews_at:
                        user.quota_gpt_used = 0
                        user.quota_claude_used = 0
                        user.plan_renews_at = next_month(now)
                except Exception:
                    pass
    @app.context_processor
    def inject_globals():
        from flask_wtf.csrf import generate_csrf
        def user_display_name(user: object | None) -> str:
            try:
                if not user:
                    return "there"
                dn = getattr(user, "display_name", None)
                if dn:
                    return str(dn).strip()
                # Prefer email local-part; split common separators, pick first token
                email = getattr(user, "email", None) or ""
                local = email.split("@")[0]
                token = re.split(r"[._-]+", local)[0]
                return token.capitalize() if token else "there"
            except Exception:
                return "there"
        def absolute_url(path: str) -> str:
            base = app.config.get("APP_BASE_URL", "").rstrip("/")
            if not path.startswith("/"):
                path = "/" + path
            return f"{base}{path}" if base else path
        # Expose CSS helper for templates
        try:
            from .static.css.css import render_stylesheets as css
        except Exception:
            def css(*_args, **_kwargs):
                return ""
        return {"app_name": "LinkerHero", "version": "0.1.0", "user_display_name": user_display_name, "absolute_url": absolute_url, "css": css, "csrf_token": generate_csrf}

    @app.cli.command("db:ping")
    def db_ping() -> None:
        session = db.session
        session.execute(text("SELECT 1"))
        print("ok")

    from .news.rss import refresh_all_feeds, refresh_category_feeds
    from .news.rss import repair_article_categories_from_source
    from .news.services import CategoryService

    @app.cli.command("rss:refresh")
    @click.option("--category", "-c", default=None, help="Category slug to refresh (or all if not specified)")
    def rss_refresh(category: str | None) -> None:
        """Refresh RSS feeds and ingest new articles."""
        # Ensure all categories exist in DB first
        CategoryService.ensure_categories_exist()
        
        if category:
            count = refresh_category_feeds(category)
            print(f"Ingested {count} articles for category: {category}")
        else:
            count = refresh_all_feeds()
            print(f"Ingested {count} articles across all categories")

    @app.cli.command("rss:purge_no_image")
    def rss_purge_no_image() -> None:
        from .models import Article
        from sqlalchemy import select
        removed = 0
        with db.session.begin():
            rows = db.session.execute(
                select(Article).where(Article.deleted_at.is_(None)).where(Article.image_url.is_(None))
            ).scalars().all()
            for a in rows:
                a.deleted_at = datetime.now(timezone.utc)
                removed += 1
        print(f"soft-deleted {removed} articles without image")

    @app.cli.command("rss:repair_categories")
    @click.option("--dry-run", is_flag=True, default=False, help="Show how many links would be repaired without writing.")
    def rss_repair_categories(dry_run: bool) -> None:
        """
        Repair article->category links using Article.source (feed URL) as source of truth.

        Use this if categories were renamed/reconfigured historically and Content Fuel filters
        show articles from the wrong category.
        """
        CategoryService.ensure_categories_exist()
        res = repair_article_categories_from_source(dry_run=dry_run)
        print(f"repaired={res['repaired']} skipped_unknown_source={res['skipped_unknown_source']}")

    from .auth.services import ensure_admin
    import click

    @app.cli.command("user:create_admin")
    @click.argument("email")
    def create_admin_cmd(email: str) -> None:
        ensure_admin(email)
        print("admin ensured")

    return app

