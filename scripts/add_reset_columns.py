from app import create_app
from app.db import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Add columns if missing (Postgres)
    db.session.execute(text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS password_reset_nonce VARCHAR(64);
    """))
    db.session.execute(text("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS password_reset_sent_at TIMESTAMPTZ;
    """))
    db.session.commit()
    print("Ensured columns exist: password_reset_nonce, password_reset_sent_at")
