from django.conf import settings
from django.contrib.auth import get_user_model, login


class AutoLoginMiddleware:
    """Auto-login the first superuser, skipping the login page.

    Controlled by settings.AUTO_LOGIN (env EASYSLIDES_AUTO_LOGIN, defaults to
    follow DEBUG), so it can be disabled independently for public deployments.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, 'AUTO_LOGIN', settings.DEBUG) and not request.user.is_authenticated:
            User = get_user_model()
            user = User.objects.filter(is_superuser=True).first()
            if user:
                login(request, user)
        return self.get_response(request)
