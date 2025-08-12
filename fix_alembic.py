from app import create_app
from app.db import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    db.session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
    before = list(db.session.execute(text("SELECT version_num FROM alembic_version")))
    print("before:", before)
    db.session.execute(text("DELETE FROM alembic_version"))
    db.session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0003_soft_delete_and_constraints')"))
    db.session.commit()
    after = list(db.session.execute(text("SELECT version_num FROM alembic_version")))
    print("after:", after)
