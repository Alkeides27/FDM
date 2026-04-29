import logging

from django_ratelimit.exceptions import Ratelimited

logger = logging.getLogger('security.ratelimit')


class RatelimitLoggingMiddleware:
    """
    Registra eventos de rate limit excedido para deteccion de abuso.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, Ratelimited):
            logger.warning(
                'Rate limit exceeded - path=%s method=%s ip=%s ua=%s username=%s',
                request.path,
                request.method,
                request.META.get('REMOTE_ADDR', 'unknown'),
                request.META.get('HTTP_USER_AGENT', '')[:200],
                request.POST.get('username', ''),
            )
        return None
