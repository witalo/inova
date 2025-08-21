"""
Django settings for inova project - PRODUCCIÓN CON HTTP Y HTTPS
"""
import os
import sys
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-3i)3+8sh1bp3pjepc0tynuhxe@(nclaei#!3mj1e6hp&wx0&ls'

# ================================
# 🔴 CONFIGURACIÓN PRINCIPAL - CAMBIAR SOLO ESTO
# ================================
DEBUG = False  # ⬅️ CAMBIAR A False PARA PRODUCCIÓN

# ================================
# CONFIGURACIÓN AUTOMÁTICA SEGÚN DEBUG
# ================================
if DEBUG:
    print("=" * 80)
    print("🔧 MODO: DESARROLLO (DEBUG=True)")
    print("=" * 80)
    # En desarrollo: permitir todo, logs visibles, puede ser síncrono
    ALLOWED_HOSTS = ['*']
    ALLOW_HTTP_IN_PRODUCTION = True
    # Celery en modo síncrono para debug (cambiar si quieres async en dev)
    USE_CELERY_ASYNC = False  # ⬅️ False = Síncrono en desarrollo
else:
    print("=" * 80)
    print("🚀 MODO: PRODUCCIÓN (DEBUG=False)")
    print("=" * 80)
    # En producción: más restrictivo, siempre asíncrono
    ALLOWED_HOSTS = ['*']
    ALLOW_HTTP_IN_PRODUCTION = True
    # Celery SIEMPRE asíncrono en producción
    USE_CELERY_ASYNC = True  # ⬅️ SIEMPRE True en producción

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'graphene_django',
    'corsheaders',
    # 'graphql_jwt.refresh_token.apps.RefreshTokenConfig',
    'operations',
    'finances',
    'products',
    'users'
]

MIDDLEWARE = [
    # 'operations.middleware.DebugGraphQLMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Middleware para logging de facturación
    'operations.middleware.BillingLoggingMiddleware',
]
# Configuración de WhiteNoise (opcional pero recomendado)
WHITENOISE_AUTOREFRESH = DEBUG  # Solo en desarrollo
WHITENOISE_USE_FINDERS = DEBUG  # Solo en desarrollo
WHITENOISE_COMPRESS_OFFLINE = not DEBUG  # Comprimir en producción

# Si usas WhiteNoise 6.0+
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

ROOT_URLCONF = 'inova.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'inova.wsgi.application'

# GraphQL Configuration
GRAPHENE = {
    "SCHEMA": "inova.inova.schema",
    "MIDDLEWARE": [
        "graphql_jwt.middleware.JSONWebTokenMiddleware",
    ],
}

AUTHENTICATION_BACKENDS = [
    "graphql_jwt.backends.JSONWebTokenBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# JWT Configuration
GRAPHQL_JWT = {
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_EXPIRATION_DELTA': timedelta(hours=24),
    # 'JWT_REFRESH_EXPIRATION_DELTA': timedelta(days=7),
    'JWT_LONG_RUNNING_REFRESH_TOKEN': False,
    'JWT_ALLOW_REFRESH': False,
    'JWT_AUTH_HEADER_PREFIX': 'Bearer',
    # 'JWT_REFRESH_TOKEN_N_BYTES': 20,
    'JWT_ALGORITHM': 'HS256',
    'JWT_SECRET_KEY': SECRET_KEY,
}

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Solo permitir todos en desarrollo
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
    "http://localhost:8080",
    "https://localhost:8080",
    "http://localhost:8000",
    "https://localhost:8000",
    "http://192.168.1.245:8000",
    "https://192.168.1.245:8000",
    "http://10.0.2.2:8000",
    "https://10.0.2.2:8000",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Security headers - Configuración según modo
SECURE_CROSS_ORIGIN_OPENER_POLICY = None

if DEBUG or ALLOW_HTTP_IN_PRODUCTION:
    # Permitir HTTP
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_PROXY_SSL_HEADER = None
    SECURE_BROWSER_XSS_FILTER = False
    SECURE_CONTENT_TYPE_NOSNIFF = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
else:
    # Forzar HTTPS en producción
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'inova'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'italo'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'OPTIONS': {
            'sql_mode': 'traditional',
        }
    }
}

# CSRF Configuration
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
    "http://localhost:8000",
    "https://localhost:8000",
    "http://192.168.1.245:8000",
    "https://192.168.1.245:8000",
]

APPEND_SLASH = False

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 6,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'es-PE'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True
DEFAULT_CHARSET = 'utf-8'
# ================================
# CONFIGURACIÓN DE ARCHIVOS ESTÁTICOS Y MEDIA
# ================================

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files - CONFIGURACIÓN CRÍTICA PARA PRODUCCIÓN
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# # Static files (CSS, JavaScript, Images)
# STATIC_URL = '/static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# STATICFILES_DIRS = [
#     os.path.join(BASE_DIR, "static"),
# ]
#
# # Media files
# MEDIA_URL = '/media/'
# MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

# ================================
# 🔥 CONFIGURACIÓN CELERY INTELIGENTE
# ================================

# Configuración base de Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# ⚡ CONFIGURACIÓN CRÍTICA DE CELERY
if USE_CELERY_ASYNC:
    # MODO ASÍNCRONO (Producción o desarrollo con Celery)
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
    print("✅ Celery: MODO ASÍNCRONO - Las tareas se ejecutarán en background")
    print("   - Las mutaciones retornarán inmediatamente")
    print("   - Necesitas tener Celery worker corriendo")
else:
    # MODO SÍNCRONO (Solo para desarrollo/debug)
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    print("⚠️  Celery: MODO SÍNCRONO - Las tareas se ejecutarán inmediatamente")
    print("   - Las mutaciones esperarán hasta completarse")
    print("   - NO necesitas Celery worker")

# Configuración de colas
CELERY_TASK_DEFAULT_QUEUE = 'celery'
CELERY_TASK_CREATE_MISSING_QUEUES = True

# Rutas de tareas con prioridad
# CELERY_TASK_ROUTES = {
#     'operations.process_electronic_billing': {
#         'queue': 'billing',
#         'routing_key': 'billing.process',
#     },
#     'operations.cancel_document': {
#         'queue': 'billing',
#         'routing_key': 'billing.cancel',
#     },
#     'operations.retry_failed_billings': {
#         'queue': 'billing',
#         'routing_key': 'billing.retry',
#     },
# }

# Configuración de workers
CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', 4))
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100  # Reiniciar worker cada 100 tareas

# Tiempo límite para tareas
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutos
CELERY_TASK_TIME_LIMIT = 600  # 10 minutos

# Configuración de resultados
CELERY_RESULT_EXPIRES = 3600  # 1 hora
CELERY_TASK_TRACK_STARTED = True

# ⚡ IMPORTANTE: Configuración para ver logs en Celery
CELERY_WORKER_HIJACK_ROOT_LOGGER = False  # No secuestrar el logger root
CELERY_WORKER_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
CELERY_WORKER_TASK_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Mostrar más información en Celery
if DEBUG:
    CELERY_TASK_SEND_SENT_EVENT = True  # Enviar eventos de tareas
    CELERY_SEND_TASK_EVENTS = True  # Enviar todos los eventos

# ================================
# CONFIGURACIÓN DE FACTURACIÓN ELECTRÓNICA
# ================================

ELECTRONIC_BILLING_ROOT = os.path.join(MEDIA_ROOT, 'electronic_billing')

SUNAT_ENDPOINTS = {
    'BETA': {
        'billing': 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService?wsdl',
        'guide': 'https://e-beta.sunat.gob.pe/ol-ti-itemision-guia-gem-beta/billService?wsdl',
    },
    'PRODUCTION': {
        'billing': 'https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService?wsdl',
        'guide': 'https://e-guiaremision.sunat.gob.pe/ol-ti-itemision-guia-gem/billService?wsdl',
    }
}

BILLING_MAX_RETRIES = int(os.environ.get('BILLING_MAX_RETRIES', 5))
BILLING_RETRY_INTERVAL_MINUTES = int(os.environ.get('BILLING_RETRY_INTERVAL_MINUTES', 30))
BILLING_TASK_TIMEOUT_SECONDS = int(os.environ.get('BILLING_TASK_TIMEOUT_SECONDS', 300))

# ================================
# 📊 CONFIGURACIÓN DE LOGGING MEJORADA
# ================================

LOGS_ROOT = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_ROOT, exist_ok=True)

# Nivel de logging según modo
LOG_LEVEL = 'DEBUG' if DEBUG else 'INFO'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'billing': {
            'format': '[BILLING] {levelname} {asctime} {module} - {message}',
            'style': '{',
        },
        'celery_format': {
            'format': '[CELERY] {levelname} {asctime} - {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file_django': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_ROOT, 'django.log'),
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',  # ← AGREGADO
            'delay': False,       # ← AGREGADO
        },
        'file_billing': {
            'level': 'DEBUG',  # ← CAMBIADO A DEBUG PARA VER TODO
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_ROOT, 'billing.log'),
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'billing',
            'encoding': 'utf-8',  # ← AGREGADO
            'delay': False,       # ← AGREGADO
        },
        'file_celery': {
            'level': 'DEBUG',  # ← CAMBIADO A DEBUG
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_ROOT, 'celery.log'),
            'maxBytes': 10485760,
            'backupCount': 5,
            'formatter': 'celery_format',
            'encoding': 'utf-8',  # ← AGREGADO
            'delay': False,       # ← AGREGADO
        },
        'file_sunat': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_ROOT, 'sunat.log'),
            'maxBytes': 5242880,
            'backupCount': 10,
            'formatter': 'billing',
            'encoding': 'utf-8',  # ← AGREGADO
            'delay': False,       # ← AGREGADO
        },
    },
    'root': {
        'handlers': ['console', 'file_billing'],  # ← AGREGADO file_billing
        'level': 'INFO',
    },
    'loggers': {
        # Django
        'django': {
            'handlers': ['console', 'file_django'],
            'level': 'INFO',
            'propagate': False,
        },
        # Operations - SIEMPRE visible en consola y archivo
        'operations': {
            'handlers': ['console', 'file_billing'],
            'level': 'DEBUG',  # ← DEBUG para ver todo
            'propagate': False,
        },
        'operations.services': {
            'handlers': ['console', 'file_billing'],
            'level': 'DEBUG',  # ← DEBUG
            'propagate': False,
        },
        'operations.tasks': {
            'handlers': ['console', 'file_billing', 'file_celery'],
            'level': 'DEBUG',  # ← DEBUG
            'propagate': False,
        },
        'operations.sunat': {
            'handlers': ['console', 'file_sunat'],
            'level': 'INFO',
            'propagate': False,
        },
        # Celery
        'celery': {
            'handlers': ['console', 'file_celery'],
            'level': 'INFO',
            'propagate': False,  # ← CAMBIADO A False
        },
        'celery.task': {
            'handlers': ['console', 'file_celery'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery.worker': {
            'handlers': ['console', 'file_celery'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
# ================================
# CONFIGURACIÓN DE CACHÉ
# ================================

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'IGNORE_EXCEPTIONS': True,
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'inova',
        'TIMEOUT': 300,
    },
    'billing': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/2'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SERIALIZER': 'django_redis.serializers.json.JSONSerializer',
        },
        'KEY_PREFIX': 'billing',
        'TIMEOUT': 1800,
    }
}

# ================================
# CONFIGURACIÓN DE SESIONES
# ================================

# SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 86400  # 24 horas

# ================================
# OTRAS CONFIGURACIONES
# ================================

APIS_NET_PE_TOKEN = "Bearer apis-token-3244.1KWBKUSrgYq6HNht68arg8LNsId9vVLm"
REQUESTS_TIMEOUT = int(os.environ.get('REQUESTS_TIMEOUT', 60))
SUNAT_REQUEST_TIMEOUT = int(os.environ.get('SUNAT_REQUEST_TIMEOUT', 120))

FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644
BILLING_FILE_UPLOAD_MAX_SIZE = 10485760  # 10MB
BILLING_FILE_PERMISSIONS = 0o600

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'users.User'

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

INTERNAL_IPS = ['127.0.0.1', 'localhost'] if DEBUG else []

# ================================
# 🚀 VERIFICACIÓN DE CONFIGURACIÓN AL INICIAR
# ================================

print("=" * 80)
print("CONFIGURACIÓN DEL SISTEMA INOVA")
print("=" * 80)
print(f"📍 Modo: {'DESARROLLO' if DEBUG else 'PRODUCCIÓN'}")
print(f"📍 Debug: {DEBUG}")
print(f"📍 Celery: {'ASÍNCRONO ✅' if USE_CELERY_ASYNC else 'SÍNCRONO ⚠️'}")
print(f"📍 Base Dir: {BASE_DIR}")
print(f"📍 Logs Dir: {LOGS_ROOT}")
print(f"📍 Media Root: {MEDIA_ROOT}")

# Verificar Redis
try:
    import redis
    r = redis.Redis.from_url(CELERY_BROKER_URL)
    r.ping()
    print(f"📍 Redis: ✅ Conectado en {CELERY_BROKER_URL}")
except Exception as e:
    print(f"📍 Redis: ❌ No disponible - {e}")

print("=" * 80)

# Mensaje de instrucciones según el modo
if USE_CELERY_ASYNC:
    print(" IMPORTANTE: Debes iniciar Celery Worker:")
    print(" celery -A inova worker -l INFO -P solo -Q billing,celery")
else:
    print("  Modo síncrono activo - No necesitas Celery Worker")
    print("  Las tareas se ejecutarán inmediatamente (puede ser lento)")

print("=" * 80)