from __future__ import annotations

import os
import subprocess

import pytest


def test_app_factory_imports():
    import app  # noqa: F401


def test_home_route_200(monkeypatch):
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    from app import create_app

    flask_app = create_app()
    client = flask_app.test_client()
    res = client.get("/")
    assert res.status_code == 200


def test_cli_db_ping(capsys, monkeypatch):
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    from app import create_app

    flask_app = create_app()
    runner = flask_app.test_cli_runner()
    result = runner.invoke(args=["db:ping"]) 
    assert result.exit_code == 0
    assert "ok" in result.output

