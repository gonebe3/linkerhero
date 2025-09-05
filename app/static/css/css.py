from __future__ import annotations

from typing import Iterable, List
from flask import url_for


def stylesheet_urls(*names: str | Iterable[str]) -> List[str]:
    """Return static CSS URLs for provided stylesheet names.

    Each name may be a filename like "spaceship.css" or a path relative to
    the static css directory. External/absolute URLs are returned as-is.
    """
    flattened: List[str] = []
    for item in names:
        if isinstance(item, (list, tuple, set)):
            flattened.extend(item)  # type: ignore[arg-type]
        else:
            flattened.append(item)
    urls: List[str] = []
    for name in flattened:
        if not name:
            continue
        s = str(name)
        if s.startswith("http://") or s.startswith("https://"):
            urls.append(s)
        else:
            # Normalize simple names to live under css/
            if "/" not in s:
                s = f"css/{s}"
            urls.append(url_for("static", filename=s))
    return urls


def render_stylesheets(*names: str | Iterable[str]) -> str:
    """Render <link rel="stylesheet"> tags for provided stylesheet names.

    Example (in Jinja): {{ css('spaceship.css', 'custom.css')|safe }}
    """
    links = [f'<link rel="stylesheet" href="{href}" />' for href in stylesheet_urls(*names)]
    return "\n".join(links)




