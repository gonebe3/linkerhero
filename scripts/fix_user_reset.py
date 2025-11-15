from app import create_app
from app.db import db
from app.models import User
from sqlalchemy import select

EMAIL = "dominikkostiuszkin@gmail.com"

app = create_app()
with app.app_context():
    u = db.session.execute(select(User).where(User.email == EMAIL)).scalar_one_or_none()
    if not u:
        print("User not found")
    else:
        u.password_reset_nonce = None
        u.password_reset_sent_at = None
        db.session.commit()
        print("Updated fields for", EMAIL)