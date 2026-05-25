from django.conf import settings
from django.contrib.auth import get_user_model, login


class AutoLoginMiddleware:
    """Auto-login the first superuser when DEBUG=True, skipping the login page."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG and not request.user.is_authenticated:
            User = get_user_model()
            user = User.objects.filter(is_superuser=True).first()
            if user:
                login(request, user)
        return self.get_response(request)
