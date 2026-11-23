class HealthCheckMiddleware:
    """Serve the database-only health endpoint before session/auth/message middleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == "/healthz":
            from .views import healthz

            return healthz(request)
        return self.get_response(request)
