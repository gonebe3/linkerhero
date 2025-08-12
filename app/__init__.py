from __future__ import annotations

from flask import Flask
from .config import Config
from .db import init_engine_and_session, db_session
from .models import Base
from sqlalchemy import text

from .main.routes import bp as main_bp
from .auth.routes import bp as auth_bp
from .news.routes import bp as news_bp
from .gen.routes import bp as gen_bp


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config())

    init_engine_and_session(app.config["SQLALCHEMY_DATABASE_URI"])  # pooled/runtime

    # Provide Alembic CLI via Flask (without Flask-SQLAlchemy)
    # This gives you `flask db` commands that proxy to Alembic using
    # the existing migrations/env.py which reads DATABASE_URL from .env
    import os
    import click
    from alembic import command as alembic_command
    from alembic.config import Config as AlembicConfig

    def _alembic_cfg() -> AlembicConfig:
        # Point to repo root alembic.ini
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        ini_path = os.path.join(repo_root, "alembic.ini")
        cfg = AlembicConfig(ini_path)
        # Ensure script location resolves to the migrations folder in repo root
        cfg.set_main_option("script_location", os.path.join(repo_root, "migrations"))
        return cfg

    @app.cli.group("db")
    def db_group() -> None:
        """Perform database migrations (Alembic)."""
        pass

    @db_group.command("current")
    def db_current() -> None:
        alembic_command.current(_alembic_cfg(), verbose=True)

    @db_group.command("heads")
    def db_heads() -> None:
        alembic_command.heads(_alembic_cfg(), verbose=True)

    @db_group.command("branches")
    def db_branches() -> None:
        alembic_command.branches(_alembic_cfg())

    @db_group.command("upgrade")
    @click.argument("rev", default="head")
    def db_upgrade(rev: str) -> None:
        alembic_command.upgrade(_alembic_cfg(), rev)

    @db_group.command("downgrade")
    @click.argument("rev", default="-1")
    def db_downgrade(rev: str) -> None:
        alembic_command.downgrade(_alembic_cfg(), rev)

    @db_group.command("revision")
    @click.option("--message", "message", "-m", default="", help="Revision message")
    @click.option("--autogenerate", is_flag=True, default=True)
    def db_revision(message: str, autogenerate: bool) -> None:
        alembic_command.revision(_alembic_cfg(), message=message, autogenerate=autogenerate)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(gen_bp)

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
    @app.context_processor
    def inject_globals():
        return {"app_name": "LinkerHero", "version": "0.1.0"}

    @app.cli.command("db:ping")
    def db_ping() -> None:
        with db_session() as session:
            session.execute(text("SELECT 1"))
        print("ok")

    from .news.rss import refresh_feeds

    @app.cli.command("rss:refresh")
    def rss_refresh() -> None:
        refresh_feeds()
        print("ingested")

    from .auth.routes import ensure_admin
    import click

    @app.cli.command("user:create_admin")
    @click.argument("email")
    def create_admin_cmd(email: str) -> None:
        ensure_admin(email)
        print("admin ensured")

    return app

