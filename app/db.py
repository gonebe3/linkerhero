from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from contextlib import contextmanager

db = SQLAlchemy()

@contextmanager
def db_session():
    session = db.session
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise

