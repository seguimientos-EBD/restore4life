from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.urls import reverse

EXEMPT_PATH_PREFIXES = (
    "/admin/",
    "/token/",
    settings.STATIC_URL,
    settings.MEDIA_URL,
)


EXEMPT_URL_NAMES = (
    settings.LOGIN_URL,
    'register',
)


class LoginRequiredMiddleware:
    """Requires authentication for every URL except login, register and the exempt prefixes above."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not self._is_exempt(request.path):
            return redirect_to_login(request.get_full_path(), login_url=reverse(settings.LOGIN_URL))
        return self.get_response(request)

    def _is_exempt(self, path):
        if path in (reverse(name) for name in EXEMPT_URL_NAMES):
            return True
        return path.startswith(EXEMPT_PATH_PREFIXES)
