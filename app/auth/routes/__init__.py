from __future__ import annotations

from flask import Blueprint

bp = Blueprint("auth", __name__, url_prefix="")

# Import route modules to register handlers with the blueprint
from . import basic  # noqa: F401,E402
from . import oauth_google  # noqa: F401,E402
from . import oauth_linkedin  # noqa: F401,E402
from . import password_reset  # noqa: F401,E402

