from decimal import Decimal

from django.shortcuts import get_object_or_404

from operations.apis import ApisNetPe
from operations.models import Operation
import pytz
from django.utils import timezone as django_timezone
import os
import mimetypes
import platform
from django.http import HttpResponse, Http404, FileResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from operations.models import Operation
import logging

logger = logging.getLogger(__name__)
APIS_TOKEN = "Bearer apis-token-3244.1KWBKUSrgYq6HNht68arg8LNsId9vVLm"
api_net = ApisNetPe(APIS_TOKEN)


def generate_next_number(serial, company_id, operation_type):
    """Genera el siguiente número correlativo para una serie"""
    last_operation = Operation.objects.filter(
        serial=serial,
        company_id=company_id,
        operation_type=operation_type
    ).order_by('-number').first()

    if last_operation:
        return last_operation.number + 1
    return 1


def calculate_operation_totals(details, igv_percent=18):
    """Calcula los totales de una operación basado en sus detalles"""
    totals = {
        'total_taxable': Decimal('0'),
        'total_unaffected': Decimal('0'),
        'total_exempt': Decimal('0'),
        'total_free': Decimal('0'),
        'total_discount': Decimal('0'),
        'total_igv': Decimal('0'),
        'total_amount': Decimal('0')
    }

    for detail in details:
        # Clasificar por tipo de afectación
        if detail.type_affectation.code == 10:  # Gravada
            totals['total_taxable'] += detail.total_value
            totals['total_igv'] += detail.total_igv
        elif detail.type_affectation.code == 20:  # Exonerada
            totals['total_exempt'] += detail.total_value
        elif detail.type_affectation.code == 30:  # Inafecta
            totals['total_unaffected'] += detail.total_value
        else:  # Gratuita
            totals['total_free'] += detail.total_value

        totals['total_discount'] += detail.total_discount

    # Total general
    totals['total_amount'] = (
            totals['total_taxable'] +
            totals['total_exempt'] +
            totals['total_unaffected'] +
            totals['total_igv']
    )

    return totals


# Funciones helper para manejo de zona horaria
def get_peru_date():
    """Obtener la fecha actual en zona horaria de Perú"""
    peru_tz = pytz.timezone('America/Lima')
    return django_timezone.now().astimezone(peru_tz).date()


def get_peru_datetime():
    """Obtener fecha y hora actual en zona horaria de Perú"""
    peru_tz = pytz.timezone('America/Lima')
    return django_timezone.now().astimezone(peru_tz)


@csrf_exempt
def serve_protected_media(request, path):
    """
    Vista para servir archivos media - Compatible con Windows y Linux
    """
    # Normalizar el path recibido (convertir / a \ en Windows o viceversa)
    if platform.system() == 'Windows':
        # En Windows, convertir / a \
        path = path.replace('/', '\\')
    else:
        # En Linux, convertir \ a /
        path = path.replace('\\', '/')

    # Construir la ruta completa del archivo
    file_path = os.path.join(settings.MEDIA_ROOT, path)

    # Normalizar la ruta para el sistema operativo actual
    file_path = os.path.normpath(file_path)

    logger.info(f"Sistema Operativo: {platform.system()}")
    logger.info(f"Path recibido: {path}")
    logger.info(f"Path completo: {file_path}")
    logger.info(f"¿Archivo existe?: {os.path.exists(file_path)}")

    # Verificar que el archivo esté dentro de MEDIA_ROOT
    if not file_path.startswith(str(settings.MEDIA_ROOT)):
        logger.warning(f"Intento de acceso fuera de MEDIA_ROOT: {file_path}")
        raise Http404("Archivo no encontrado")

    # Verificar que el archivo existe
    if not os.path.exists(file_path):
        # Intentar con diferentes combinaciones de separadores
        alternate_paths = [
            file_path.replace('\\', '/'),
            file_path.replace('/', '\\'),
            os.path.join(settings.MEDIA_ROOT, path.replace('\\', '/')),
            os.path.join(settings.MEDIA_ROOT, path.replace('/', '\\'))
        ]

        file_found = False
        for alt_path in alternate_paths:
            if os.path.exists(alt_path):
                file_path = alt_path
                file_found = True
                logger.info(f"Archivo encontrado en ruta alternativa: {alt_path}")
                break

        if not file_found:
            logger.error(f"Archivo no encontrado en ninguna variante: {file_path}")
            raise Http404("Archivo no encontrado")

    try:
        # Detectar el tipo MIME
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        # Abrir y servir el archivo
        response = FileResponse(
            open(file_path, 'rb'),
            content_type=mime_type
        )

        # Configurar headers
        filename = os.path.basename(file_path)

        # Para archivos XML y ZIP, forzar descarga
        if file_path.endswith(('.xml', '.zip', '.pdf')):
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
        else:
            response['Content-Disposition'] = f'inline; filename="{filename}"'

        response['X-Content-Type-Options'] = 'nosniff'
        response['Access-Control-Allow-Origin'] = '*'  # Para CORS

        logger.info(f"✅ Archivo servido exitosamente: {filename}")
        return response

    except IOError as e:
        logger.error(f"Error al leer archivo: {e}")
        raise Http404("Error al leer el archivo")


@csrf_exempt
def download_billing_file(request, file_type, filename):
    """
    Vista para descargar archivos de facturación por tipo y nombre
    """
    logger.info(f"=== DESCARGA SOLICITADA ===")
    logger.info(f"Tipo: {file_type}")
    logger.info(f"Archivo: {filename}")

    # Mapear tipo de archivo a carpeta
    folder_map = {
        'xml': 'XML',
        'signed': 'FIRMA',
        'cdr': 'CDR',
        'pdf': 'PDF',
        'cancellation_xml': 'BAJA/XML',
        'cancellation_signed': 'BAJA/FIRMA',
        'cancellation_cdr': 'BAJA/CDR'
    }

    folder = folder_map.get(file_type)
    if not folder:
        logger.error(f"Tipo de archivo no válido: {file_type}")
        raise Http404("Tipo de archivo no válido")

    # Buscar el archivo en la base de datos
    try:
        # Buscar por nombre de archivo en cualquier operación
        from django.db.models import Q

        operations = Operation.objects.filter(
            Q(xml_file_path__icontains=filename) |
            Q(cdr_file_path__icontains=filename) |
            Q(signed_xml_file_path__icontains=filename)|
            Q(cancellation_xml_path__icontains=filename) |
            Q(cancellation_signed_xml_path__icontains=filename) |
            Q(cancellation_cdr_path__icontains=filename)
        )

        if operations.exists():
            operation = operations.first()

            # Obtener el archivo según el tipo
            if file_type == 'xml' and operation.xml_file_path:
                file_path = operation.xml_file_path
            elif file_type == 'cdr' and operation.cdr_file_path:
                file_path = operation.cdr_file_path
            elif file_type == 'signed' and operation.signed_xml_file_path:
                file_path = operation.signed_xml_file_path
            elif file_type == 'cancellation_xml' and operation.cancellation_xml_path:
                file_path = operation.cancellation_xml_path
            elif file_type == 'cancellation_signed' and operation.cancellation_signed_xml_path:
                file_path = operation.cancellation_signed_xml_path
            elif file_type == 'cancellation_cdr' and operation.cancellation_cdr_path:
                file_path = operation.cancellation_cdr_path
            # else:
            #     # Si no está en la BD, construir la ruta
            #     ruc = operation.company.ruc if operation.company else filename.split('-')[0]
            #     relative_path = f"electronic_billing{os.sep}{ruc}{os.sep}{folder}{os.sep}{filename}"
            #     return serve_protected_media(request, relative_path)

            # Servir el archivo directamente si existe
            if os.path.exists(file_path):
                logger.info(f"Sirviendo archivo desde BD: {file_path}")

                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type is None:
                    mime_type = 'application/octet-stream'

                response = FileResponse(
                    open(file_path, 'rb'),
                    content_type=mime_type
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                response['Access-Control-Allow-Origin'] = '*'
                return response

        # Si no está en la BD, intentar con el RUC del filename
        # Formato esperado: 20608433474-01-F001-1.xml
        parts = filename.split('-')
        if len(parts) >= 4:
            ruc = parts[0]
        else:
            raise Http404("Formato de archivo no válido")

        # Construir path relativo
        relative_path = f"electronic_billing{os.sep}{ruc}{os.sep}{folder}{os.sep}{filename}"

        return serve_protected_media(request, relative_path)

    except Exception as e:
        logger.error(f"Error procesando descarga: {e}")
        raise Http404(f"Error procesando archivo: {str(e)}")


@csrf_exempt
def download_operation_file(request, operation_id, file_type):
    """
    Descargar archivo por ID de operación
    """
    logger.info(f"Descarga por operación ID: {operation_id}, tipo: {file_type}")

    operation = get_object_or_404(Operation, id=operation_id)

    # Obtener el path del archivo según el tipo
    if file_type == 'xml' and operation.xml_file_path:
        file_path = operation.xml_file_path
    elif file_type == 'cdr' and operation.cdr_file_path:
        file_path = operation.cdr_file_path
    elif file_type == 'signed' and operation.signed_xml_file_path:
        file_path = operation.signed_xml_file_path
    elif file_type == 'cancellation_xml' and operation.cancellation_xml_path:
        file_path = operation.cancellation_xml_path
    elif file_type == 'cancellation_signed' and operation.cancellation_signed_xml_path:
        file_path = operation.cancellation_signed_xml_path
    elif file_type == 'cancellation_cdr' and operation.cancellation_cdr_path:
        file_path = operation.cancellation_cdr_path
    else:
        logger.error(f"Tipo de archivo no disponible: {file_type}")
        raise Http404("Archivo no disponible")

    # Verificar que el archivo existe
    if not os.path.exists(file_path):
        logger.error(f"Archivo no existe: {file_path}")
        raise Http404("El archivo no existe en el servidor")

    try:
        # Servir el archivo directamente
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        response = FileResponse(
            open(file_path, 'rb'),
            content_type=mime_type
        )

        filename = os.path.basename(file_path)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Access-Control-Allow-Origin'] = '*'

        logger.info(f"✅ Archivo servido: {filename}")
        return response

    except Exception as e:
        logger.error(f"Error sirviendo archivo: {e}")
        raise Http404(f"Error al servir archivo: {str(e)}")