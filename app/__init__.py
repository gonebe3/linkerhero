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

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(gen_bp)

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

