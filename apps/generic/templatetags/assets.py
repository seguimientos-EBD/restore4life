"""Cache busting for the static files this project writes itself.

The dev server sends static files with a `Last-Modified` and nothing else — no
`ETag`, no `Cache-Control` — and the URLs never change. A browser with no freshness
information to go on falls back to a heuristic, keeps its copy for a while and does
not even ask, so an edited stylesheet or script can go unnoticed for minutes.

That is untidy for CSS and breaks the page outright for JavaScript, because the
markup and the script that drives it stop matching. Hanging the file's modification
time off the URL turns every edit into a new URL, which no cache can answer from.
"""

import os

from django import template
from django.contrib.staticfiles import finders

register = template.Library()


@register.simple_tag
def asset_mtime(path):
    """Modification time of a static file, or 0 when it cannot be found.

    Never raises: a missing file has to end up as a request the server answers with a
    404, not as a 500 rendering the page.
    """
    absolute = finders.find(path)
    if not absolute:
        return 0
    try:
        return int(os.path.getmtime(absolute))
    except OSError:
        return 0


@register.simple_tag
def asset_exists(path):
    """Whether a static file is actually there.

    The manual is written before its screenshots are taken, so its figures have to be
    able to ask. Same contract as `asset_mtime`: it never raises, and a file it cannot
    find is simply absent.
    """
    return bool(finders.find(path))
