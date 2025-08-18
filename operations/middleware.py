# ================================
# 15. MIDDLEWARE PARA LOGGING
# ================================

# operations/middleware.py
import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('operations.services')


class BillingLoggingMiddleware(MiddlewareMixin):
    """Middleware para logging de operaciones de facturación"""

    def process_request(self, request):
        request.start_time = time.time()

    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time

            if 'billing' in request.path or 'operation' in request.path:
                logger.info(
                    f"Request: {request.method} {request.path} "
                    f"Status: {response.status_code} "
                    f"Duration: {duration:.2f}s "
                    f"User: {getattr(request.user, 'username', 'Anonymous')}"
                )

        return response