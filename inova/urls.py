"""
URL configuration for inova project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView
from django.conf.urls.static import static
from django.urls import path, re_path
from inova.schema import schema
from inova import settings
from operations.views import download_billing_file, serve_protected_media, download_operation_file

urlpatterns = [
    path('admin/', admin.site.urls),
    path("graphql", csrf_exempt(GraphQLView.as_view(graphiql=True, schema=schema))),
    # URLs para descarga de archivos
    path('download/<str:file_type>/<str:filename>/', download_billing_file, name='download_billing'),
    path('download/operation/<int:operation_id>/<str:file_type>/', download_operation_file, name='download_operation'),

    # URL general para servir archivos media
    re_path(r'^media/(?P<path>.*)$', serve_protected_media, name='media'),
]
# ✅ Agregar soporte para archivos estáticos y multimedia
# IMPORTANTE: Esta configuración funciona tanto en desarrollo como en producción
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)