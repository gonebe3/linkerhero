from __future__ import annotations

import os

from app import create_app


def main() -> None:
    app = create_app()

    # Prefer conventional Flask env vars, fall back to sensible defaults
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("PORT") or os.getenv("FLASK_RUN_PORT") or "5000")
    debug = os.getenv("FLASK_ENV", "development").lower() != "production"

    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()


