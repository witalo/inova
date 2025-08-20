# operations/middleware.py - Crear este archivo para debug
# operations/middleware.py - REEMPLAZA todo el contenido con esto:

# import json
# import logging
# from django.utils.deprecation import MiddlewareMixin
# from django.http import JsonResponse

# logger = logging.getLogger(__name__)
#
#
# class DebugGraphQLMiddleware(MiddlewareMixin):
#     """Middleware para capturar TODOS los requests a GraphQL"""
#
#     def process_request(self, request):
#         # CAPTURAR TODO request a /graphql
#         if '/graphql' in request.path:
#             print("\n" + "🔴" * 30)
#             print(f"⚠️  GRAPHQL REQUEST DETECTADO - {request.method}")
#             print("🔴" * 30)
#
#             # Info básica
#             print(f"📍 Path: {request.path}")
#             print(f"📍 Method: {request.method}")
#             print(f"📍 IP: {self.get_client_ip(request)}")
#             print(f"📍 User-Agent: {request.META.get('HTTP_USER_AGENT', 'NO USER AGENT')}")
#             print(f"📍 Origin: {request.META.get('HTTP_ORIGIN', 'NO ORIGIN')}")
#             print(f"📍 Referer: {request.META.get('HTTP_REFERER', 'NO REFERER')}")
#             print(f"📍 Content-Type: {request.META.get('CONTENT_TYPE', 'NO CONTENT TYPE')}")
#
#             # Ver TODOS los headers
#             print("\n📋 TODOS LOS HEADERS:")
#             for key, value in request.META.items():
#                 if key.startswith('HTTP_'):
#                     header_name = key[5:].replace('_', '-')
#                     print(f"   {header_name}: {value[:100]}")
#
#             # Si es POST, ver el body
#             if request.method == 'POST':
#                 try:
#                     body = request.body.decode('utf-8')
#                     print(f"\n📦 BODY (length: {len(body)}):")
#
#                     if body:
#                         # Intentar parsear como JSON
#                         try:
#                             data = json.loads(body)
#                             print(f"   Query: {data.get('query', 'NO QUERY')[:500]}")
#                             print(f"   Variables: {data.get('variables', {})}")
#                             print(f"   OperationName: {data.get('operationName', 'NO OPERATION NAME')}")
#                         except json.JSONDecodeError:
#                             print(f"   Raw body: {body[:500]}")
#                             print(f"   ⚠️ NO ES JSON VÁLIDO")
#                     else:
#                         print("   ⚠️ BODY VACÍO")
#
#                     # Recrear el body para Django
#                     request._body = body.encode('utf-8')
#
#                 except Exception as e:
#                     print(f"   ❌ Error leyendo body: {e}")
#                     print(f"   Request.__dict__: {request.__dict__}")
#
#             # Si es un bad request, interceptarlo aquí
#             if request.method == 'POST' and not request.body:
#                 print("\n❌ REQUEST SIN BODY - ESTO CAUSA EL 400 ERROR")
#                 return JsonResponse({
#                     'error': 'Empty request body',
#                     'debug': {
#                         'ip': self.get_client_ip(request),
#                         'user_agent': request.META.get('HTTP_USER_AGENT', ''),
#                         'origin': request.META.get('HTTP_ORIGIN', ''),
#                     }
#                 }, status=400)
#
#             print("🔴" * 30 + "\n")
#
#         return None
#
#     def process_response(self, request, response):
#         """Capturar la respuesta también"""
#         if '/graphql' in request.path and response.status_code == 400:
#             print(f"⚠️  RESPONSE 400 para GraphQL")
#             print(f"   Content: {response.content[:200] if hasattr(response, 'content') else 'NO CONTENT'}")
#         return response
#
#     def get_client_ip(self, request):
#         """Obtener IP real del cliente"""
#         x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#         if x_forwarded_for:
#             ip = x_forwarded_for.split(',')[0]
#         else:
#             ip = request.META.get('REMOTE_ADDR')
#         return ip
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