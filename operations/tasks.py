from __future__ import absolute_import, unicode_literals
# ================================
# 3. TASKS PARA PROCESAMIENTO ASÍNCRONO
# ================================
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger('operations.tasks')


@shared_task(bind=True, max_retries=3, name='operations.process_electronic_billing')
def process_electronic_billing_task(self, operation_id):
    """Task para procesar facturación electrónica en segundo plano"""
    try:
        logger.info("=======>|| TASK INICIADO - operation_id: %s", operation_id)
        # print(f"TASK INICIADO - operation_id: {operation_id}")

        # Importar aquí para evitar imports circulares
        from operations.models import Operation
        from operations.services.billing_service import BillingService

        # Verificar que la operación existe
        try:
            operation = Operation.objects.get(id=operation_id)
            logger.info(f"Operación encontrada: {operation}")
        except Operation.DoesNotExist:
            logger.error(f"Operación {operation_id} no encontrada")
            return {"status": "error", "message": f"Operación {operation_id} no encontrada"}

        # Verificar estado
        if operation.billing_status in ['ACCEPTED', 'CANCELLED']:
            logger.info(f"Operación {operation_id} ya procesada: {operation.billing_status}")
            return {"status": "skipped", "message": f"Operación ya procesada: {operation.billing_status}"}

        # Actualizar estado a procesando
        operation.billing_status = 'PROCESSING'
        operation.save()

        # Procesar facturación
        logger.info(f"Iniciando BillingService para operación {operation_id}")
        billing_service = BillingService(operation_id)
        success = billing_service.process_electronic_billing()

        if success:
            logger.info(f"Facturación exitosa para operación {operation_id}")
            return {"status": "success", "message": f"Facturación procesada exitosamente: {operation_id}"}
        else:
            logger.error(f"Error en facturación para operación {operation_id}")
            raise Exception("Error en procesamiento de facturación")

    except Exception as e:
        logger.error(f"Error crítico en task {operation_id}: {str(e)}", exc_info=True)

        # Reintentar si es posible
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            logger.info(f"Reintentando en {countdown} segundos...")
            raise self.retry(exc=e, countdown=countdown)
        else:
            # Actualizar estado después de agotar reintentos
            try:
                from operations.models import Operation
                operation = Operation.objects.get(id=operation_id)
                operation.billing_status = 'ERROR'
                operation.sunat_error_description = f"Error después de {self.max_retries} reintentos: {str(e)}"
                operation.save()
            except:
                pass

            return {"status": "error", "message": f"Error final: {str(e)}"}


@shared_task(bind=True, max_retries=3, name='operations.cancel_document')
def cancel_document_task(self, operation_id, reason_code='01', description='Anulación de la operación'):
    """Task para anular documento en segundo plano"""
    try:
        logger.info(f"TASK ANULACIÓN INICIADO - operation_id: %s", str(operation_id))

        from operations.models import Operation
        from operations.services.cancellation_service import CancellationService

        # Verificar que la operación existe
        try:
            operation = Operation.objects.get(id=operation_id)
            logger.info(f"Operación encontrada para anular: {operation}")
        except Operation.DoesNotExist:
            logger.error(f"Operación {operation_id} no encontrada")
            return {"status": "error", "message": f"Operación {operation_id} no encontrada"}

        # ⚠️ IMPORTANTE: Cambiar el estado AQUÍ, no en la mutación
        # Solo cambiar si está en estado válido para anulación
        if operation.billing_status in ['ACCEPTED', 'ACCEPTED_WITH_OBSERVATIONS']:
            operation.billing_status = 'PROCESSING_CANCELLATION'
            operation.save()
            logger.info(f"Estado cambiado a PROCESSING_CANCELLATION")
        else:
            # Si el estado no es válido, verificar si es un reintento
            if operation.billing_status == 'PROCESSING_CANCELLATION':
                logger.warning(f"Ya está en proceso de anulación, continuando...")
                # Permitir continuar si ya está en proceso (puede ser un reintento)
            elif operation.billing_status == 'CANCELLED':
                logger.info(f"Documento ya anulado")
                return {"status": "success", "message": "Documento ya fue anulado previamente"}
            else:
                logger.error(f"Estado no válido para anulación: {operation.billing_status}")
                return {"status": "error", "message": f"Estado no válido: {operation.billing_status}"}

        # Procesar anulación
        logger.info(f"Iniciando CancellationService para operación {operation_id}")
        cancellation_service = CancellationService(operation)

        # Temporalmente cambiar el estado para que pase la validación del servicio
        original_status = operation.billing_status
        operation.billing_status = 'ACCEPTED'  # Temporal para pasar validación

        try:
            success = cancellation_service.cancel_document(reason_code, description)
        except Exception as e:
            # Si falla, restaurar el estado original
            operation.billing_status = original_status
            operation.save()
            raise

        if success:
            logger.info(f"Documento anulado exitosamente: {operation}")
            return {"status": "success", "message": f"Documento anulado exitosamente: {operation}"}
        else:
            raise Exception("Error en anulación de documento")

    except Exception as e:
        logger.error(f"Error en task de anulación: {str(e)}", exc_info=True)

        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            logger.info(f"Reintentando anulación en {countdown} segundos...")
            raise self.retry(exc=e, countdown=countdown)
        else:
            try:
                from operations.models import Operation
                operation = Operation.objects.get(id=operation_id)
                operation.billing_status = 'CANCELLATION_ERROR'
                operation.sunat_error_description = f"Error en anulación después de {self.max_retries} reintentos: {str(e)}"
                operation.save()
            except:
                pass

            return {"status": "error", "message": f"Error final en anulación: {str(e)}"}


@shared_task(name='operations.retry_failed_billings')
def retry_failed_billings():
    """Task para reintentar facturaciones fallidas"""
    from operations.models import Operation

    # Buscar operaciones que necesitan reintento
    failed_operations = Operation.objects.filter(
        billing_status__in=['ERROR', 'PENDING'],
        retry_count__lt=5,
        last_retry_at__lt=timezone.now() - timedelta(minutes=30)
    )

    count = 0
    for operation in failed_operations:
        process_electronic_billing_task.delay(operation.id)
        logger.info(f"Reenviando facturación para: {operation}")
        count += 1

    return f"Se reenviaron {count} facturaciones"


@shared_task(name='operations.check_cancellation_ticket')
def check_cancellation_ticket_task(operation_id):
    """Task para consultar estado de ticket de anulación"""
    try:
        from operations.models import Operation
        from operations.services.cancellation_service import CancellationService

        operation = Operation.objects.get(id=operation_id)

        if not operation.cancellation_ticket:
            return {"status": "error", "message": "No hay ticket para consultar"}

        # Consultar estado del ticket
        cancellation_service = CancellationService(operation)
        success = cancellation_service._check_ticket_status(operation.cancellation_ticket)

        if success:
            return {"status": "success", "message": f"Estado de anulación consultado para: {operation}"}
        else:
            return {"status": "error", "message": "Error consultando estado de anulación"}

    except Exception as e:
        logger.error(f"Error consultando ticket: {str(e)}")
        return {"status": "error", "message": str(e)}


@shared_task(name='operations.health_check_sunat')
def health_check_sunat():
    """Task para verificar estado de servicios SUNAT"""
    try:
        from operations.services.billing_service import BillingConfiguration
        import requests

        config = BillingConfiguration()
        results = {}

        for env in ['BETA', 'PRODUCTION']:
            endpoint = config.SUNAT_ENDPOINTS[env]['billing']
            try:
                response = requests.get(endpoint, timeout=10)
                results[env] = f"OK - Status: {response.status_code}"
                logger.info(f"SUNAT {env}: {response.status_code}")
            except requests.RequestException as e:
                results[env] = f"ERROR - {str(e)}"
                logger.warning(f"SUNAT {env} no disponible: {str(e)}")

        return results

    except Exception as e:
        logger.error(f"Error en health check: {str(e)}")
        return {"error": str(e)}