from __future__ import annotations

from flask import Flask
import re
from .config import Config
from .db import db, db_session
from sqlalchemy import text

from .main.routes import bp as main_bp
from .auth.routes import bp as auth_bp
from .news.routes import bp as news_bp
from .gen.routes import bp as gen_bp
from .billing import bp as billing_bp


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config())
    # Increase max upload size to 50 MB for file-based generation
    app.config.setdefault("MAX_CONTENT_LENGTH", 50 * 1024 * 1024)

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
        return {"app_name": "LinkerHero", "version": "0.1.0", "user_display_name": user_display_name, "absolute_url": absolute_url}

    @app.cli.command("db:ping")
    def db_ping() -> None:
        session = db.session
        session.execute(text("SELECT 1"))
        print("ok")

    from .news.rss import refresh_feeds

    @app.cli.command("rss:refresh")
    def rss_refresh() -> None:
        refresh_feeds()
        print("ingested")

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

    from .auth.routes import ensure_admin
    import click

    @app.cli.command("user:create_admin")
    @click.argument("email")
    def create_admin_cmd(email: str) -> None:
        ensure_admin(email)
        print("admin ensured")

    return app

