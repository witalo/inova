# ================================
# 7. MANAGEMENT COMMANDS
# ================================
# operations/management/commands/billing_daemon.py
"""
Management Command para procesamiento automático de facturación electrónica SUNAT
Procesa documentos pendientes, reintentos y anulaciones
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import F, Q
from datetime import timedelta, datetime
import time
import logging
import signal
import sys
import traceback
from decimal import Decimal

logger = logging.getLogger('operations.billing_daemon')


class Command(BaseCommand):
    help = 'Demonio inteligente para procesamiento de facturación electrónica SUNAT'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True
        self.stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'cancellations': 0,
            'errors': []
        }

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=3600,  # 1 hora por defecto
            help='Intervalo de verificación en segundos (default: 3600 = 1 hora)'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Cantidad máxima de documentos a procesar por lote (default: 10)'
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=5,
            help='Máximo número de reintentos por documento (default: 5)'
        )
        parser.add_argument(
            '--retry-after',
            type=int,
            default=30,
            help='Minutos a esperar antes de reintentar (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar en modo simulación sin enviar a SUNAT'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Ejecutar solo una vez y salir'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mostrar información detallada de cada proceso'
        )

    def handle(self, *args, **options):
        """Manejador principal del comando"""
        self.interval = options['interval']
        self.batch_size = options['batch_size']
        self.max_retries = options['max_retries']
        self.retry_after = options['retry_after']
        self.dry_run = options['dry_run']
        self.once = options['once']
        self.verbose = options['verbose']

        # Configurar manejadores de señales
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        # Mensaje de inicio
        self.print_header()

        # Bucle principal
        cycle_count = 0
        while self.running:
            try:
                cycle_count += 1
                self.stdout.write(
                    self.style.MIGRATE_HEADING(
                        f"\n{'=' * 80}\n"
                        f"📊 CICLO #{cycle_count} - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"{'=' * 80}"
                    )
                )

                # Resetear estadísticas del ciclo
                self.reset_cycle_stats()

                # 1. Procesar documentos pendientes nuevos
                self.process_pending_documents()

                # 2. Reintentar documentos con error
                self.retry_failed_documents()

                # 3. Procesar anulaciones pendientes
                self.process_pending_cancellations()

                # 4. Verificar tickets de anulación pendientes
                self.check_cancellation_tickets()

                # 5. Limpiar y optimizar
                self.cleanup_old_errors()

                # Mostrar resumen del ciclo
                self.print_cycle_summary(cycle_count)

                # Si es ejecución única, salir
                if self.once:
                    self.stdout.write(
                        self.style.SUCCESS('\n✅ Ejecución única completada')
                    )
                    break

                # Esperar hasta el siguiente ciclo
                self.wait_next_cycle()

            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING('\n⚠️ Deteniendo demonio por señal de interrupción...')
                )
                break

            except Exception as e:
                logger.error(f"❌ Error crítico en ciclo {cycle_count}: {str(e)}", exc_info=True)
                self.stats['errors'].append({
                    'cycle': cycle_count,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })

                if not self.once:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Error en ciclo: {str(e)}. Esperando para reintentar...')
                    )
                    time.sleep(60)  # Esperar 1 minuto antes de continuar
                else:
                    raise

        # Mostrar resumen final
        self.print_final_summary()

    def process_pending_documents(self):
        """Procesar documentos pendientes de envío a SUNAT"""
        from operations.models import Operation

        self.stdout.write(
            self.style.MIGRATE_LABEL('\n📋 PROCESANDO DOCUMENTOS PENDIENTES...')
        )

        # Buscar documentos pendientes
        pending_operations = Operation.objects.filter(
            Q(billing_status='PENDING') | Q(billing_status='ERROR'),
            operation_type='S',  # Solo ventas
            company__is_billing=True,  # Solo empresas con facturación activa
            document__code__in=['01', '03', '07', '08']  # Facturas, Boletas, NC, ND
        ).select_related(
            'document', 'company', 'person'
        ).order_by('created_at')[:self.batch_size]

        if not pending_operations:
            self.stdout.write('  ℹ️ No hay documentos pendientes')
            return

        self.stdout.write(f'  📦 Encontrados: {len(pending_operations)} documentos')

        for operation in pending_operations:
            try:
                doc_info = f"{operation.serial}-{operation.number}"
                doc_type = operation.document.description if operation.document else 'DOCUMENTO'

                if self.verbose:
                    self.stdout.write(
                        f'\n  🔄 Procesando {doc_type} {doc_info}...'
                    )

                # Verificar si no está siendo procesado actualmente
                if operation.billing_status == 'PROCESSING':
                    self.stdout.write(
                        self.style.WARNING(f'    ⏳ {doc_info} ya está siendo procesado')
                    )
                    self.stats['skipped'] += 1
                    continue

                # Verificar límite de reintentos
                if operation.retry_count >= self.max_retries:
                    self.stdout.write(
                        self.style.ERROR(f'    ❌ {doc_info} superó el límite de reintentos ({self.max_retries})')
                    )
                    self.stats['skipped'] += 1
                    continue

                if self.dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ [DRY RUN] {doc_info} sería procesado')
                    )
                    self.stats['processed'] += 1
                else:
                    # Procesar el documento
                    success = self.send_document_to_sunat(operation)

                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(f'    ✅ {doc_info} enviado exitosamente')
                        )
                        self.stats['success'] += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'    ❌ {doc_info} falló el envío')
                        )
                        self.stats['failed'] += 1

                    self.stats['processed'] += 1

                    # Pequeña pausa entre documentos
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error procesando {operation}: {str(e)}", exc_info=True)
                self.stats['failed'] += 1
                self.stats['errors'].append({
                    'operation': str(operation),
                    'error': str(e)
                })

    def retry_failed_documents(self):
        """Reintentar documentos que fallaron anteriormente"""
        from operations.models import Operation

        self.stdout.write(
            self.style.MIGRATE_LABEL('\n🔄 REINTENTANDO DOCUMENTOS FALLIDOS...')
        )

        # Calcular tiempo mínimo desde último intento
        retry_time = timezone.now() - timedelta(minutes=self.retry_after)

        # Buscar documentos para reintentar
        failed_operations = Operation.objects.filter(
            billing_status__in=['ERROR', 'REJECTED'],
            retry_count__lt=self.max_retries,
            operation_type='S',
            company__is_billing=True,
            last_retry_at__lt=retry_time
        ).select_related(
            'document', 'company', 'person'
        ).order_by('retry_count', 'created_at')[:self.batch_size]

        if not failed_operations:
            self.stdout.write('  ℹ️ No hay documentos para reintentar')
            return

        self.stdout.write(f'  🔁 Reintentando: {len(failed_operations)} documentos')

        for operation in failed_operations:
            try:
                doc_info = f"{operation.serial}-{operation.number}"
                retry_info = f"(intento {operation.retry_count + 1}/{self.max_retries})"

                if self.verbose:
                    self.stdout.write(
                        f'\n  🔄 Reintentando {doc_info} {retry_info}...'
                    )

                if self.dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ [DRY RUN] {doc_info} sería reintentado')
                    )
                else:
                    # Incrementar contador de reintentos
                    operation.retry_count += 1
                    operation.last_retry_at = timezone.now()
                    operation.save(update_fields=['retry_count', 'last_retry_at'])

                    # Reintentar envío
                    success = self.send_document_to_sunat(operation)

                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(f'    ✅ {doc_info} enviado exitosamente {retry_info}')
                        )
                        self.stats['success'] += 1
                    else:
                        remaining = self.max_retries - operation.retry_count
                        if remaining > 0:
                            self.stdout.write(
                                self.style.WARNING(f'    ⚠️ {doc_info} falló. Quedan {remaining} reintentos')
                            )
                        else:
                            self.stdout.write(
                                self.style.ERROR(f'    ❌ {doc_info} agotó todos los reintentos')
                            )
                        self.stats['failed'] += 1

                    # Pausa entre reintentos
                    time.sleep(2)

            except Exception as e:
                logger.error(f"Error reintentando {operation}: {str(e)}", exc_info=True)
                self.stats['failed'] += 1

    def process_pending_cancellations(self):
        """Procesar anulaciones pendientes"""
        from operations.models import Operation

        self.stdout.write(
            self.style.MIGRATE_LABEL('\n🚫 PROCESANDO ANULACIONES PENDIENTES...')
        )

        # Buscar anulaciones pendientes o con error
        pending_cancellations = Operation.objects.filter(
            Q(billing_status='PROCESSING_CANCELLATION') |
            Q(billing_status='CANCELLATION_ERROR') |
            Q(billing_status='CANCELLATION_PENDING'),
            company__is_billing=True
        ).exclude(
            cancellation_date__isnull=True
        ).select_related(
            'document', 'company', 'person'
        ).order_by('cancellation_date')[:self.batch_size]

        if not pending_cancellations:
            self.stdout.write('  ℹ️ No hay anulaciones pendientes')
            return

        self.stdout.write(f'  🚫 Encontradas: {len(pending_cancellations)} anulaciones')

        for operation in pending_cancellations:
            try:
                doc_info = f"{operation.serial}-{operation.number}"

                if self.verbose:
                    self.stdout.write(
                        f'\n  🚫 Procesando anulación de {doc_info}...'
                    )

                if self.dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ [DRY RUN] {doc_info} sería anulado')
                    )
                    self.stats['cancellations'] += 1
                else:
                    # Procesar anulación
                    success = self.process_cancellation(operation)

                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(f'    ✅ {doc_info} anulado exitosamente')
                        )
                        self.stats['cancellations'] += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'    ❌ {doc_info} falló la anulación')
                        )
                        self.stats['failed'] += 1

                    # Pausa entre anulaciones
                    time.sleep(2)

            except Exception as e:
                logger.error(f"Error anulando {operation}: {str(e)}", exc_info=True)
                self.stats['failed'] += 1

    def check_cancellation_tickets(self):
        """Verificar estado de tickets de anulación pendientes"""
        from operations.models import Operation

        self.stdout.write(
            self.style.MIGRATE_LABEL('\n🎫 VERIFICANDO TICKETS DE ANULACIÓN...')
        )

        # Buscar operaciones con tickets pendientes
        pending_tickets = Operation.objects.filter(
            billing_status='CANCELLATION_PENDING',
            cancellation_ticket__isnull=False
        ).exclude(
            cancellation_ticket=''
        ).select_related('company')[:self.batch_size]

        if not pending_tickets:
            self.stdout.write('  ℹ️ No hay tickets pendientes')
            return

        self.stdout.write(f'  🎫 Verificando: {len(pending_tickets)} tickets')

        for operation in pending_tickets:
            try:
                doc_info = f"{operation.serial}-{operation.number}"
                ticket = operation.cancellation_ticket

                if self.verbose:
                    self.stdout.write(
                        f'\n  🎫 Verificando ticket {ticket} para {doc_info}...'
                    )

                if self.dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ [DRY RUN] Ticket {ticket} sería verificado')
                    )
                else:
                    # Verificar estado del ticket
                    from operations.services.cancellation_service import CancellationService

                    service = CancellationService(operation)
                    success = service._check_ticket_status(ticket)

                    if success:
                        self.stdout.write(
                            self.style.SUCCESS(f'    ✅ Ticket {ticket} procesado')
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'    ⏳ Ticket {ticket} aún pendiente')
                        )

                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error verificando ticket {operation.cancellation_ticket}: {str(e)}")

    def send_document_to_sunat(self, operation):
        """Enviar documento a SUNAT usando el servicio de facturación"""
        try:
            # Verificar si ya tiene XML generado
            regenerate = False
            if not operation.xml_file_path or not operation.signed_xml_file_path:
                regenerate = True
                if self.verbose:
                    self.stdout.write('      📝 Generando XML...')

            # Usar el servicio de facturación existente
            from operations.services.billing_service import BillingService

            # Actualizar estado
            operation.billing_status = 'PROCESSING'
            operation.save(update_fields=['billing_status'])

            # Procesar facturación
            billing_service = BillingService(operation.id)
            success = billing_service.process_electronic_billing()

            if success:
                logger.info(f"✅ Documento {operation} enviado exitosamente")
                return True
            else:
                logger.error(f"❌ Fallo envío de {operation}")
                return False

        except Exception as e:
            logger.error(f"Error enviando {operation}: {str(e)}", exc_info=True)

            # Actualizar estado de error
            operation.billing_status = 'ERROR'
            operation.sunat_error_description = str(e)[:500]
            operation.save(update_fields=['billing_status', 'sunat_error_description'])

            return False

    def process_cancellation(self, operation):
        """Procesar anulación de documento"""
        try:
            from operations.services.cancellation_service import CancellationService

            # Verificar si ya tiene ticket
            if operation.cancellation_ticket and operation.billing_status == 'CANCELLATION_PENDING':
                if self.verbose:
                    self.stdout.write(f'      🎫 Ya tiene ticket: {operation.cancellation_ticket}')
                # Solo verificar estado
                service = CancellationService(operation)
                return service._check_ticket_status(operation.cancellation_ticket)

            # Procesar nueva anulación
            service = CancellationService(operation)
            success = service.cancel_document(
                operation.cancellation_reason or '01',
                operation.cancellation_description or 'Anulación de la operación'
            )

            if success:
                logger.info(f"✅ Documento {operation} anulado exitosamente")
                return True
            else:
                logger.error(f"❌ Fallo anulación de {operation}")
                return False

        except Exception as e:
            logger.error(f"Error anulando {operation}: {str(e)}", exc_info=True)

            # Actualizar estado de error
            operation.billing_status = 'CANCELLATION_ERROR'
            operation.sunat_error_description = str(e)[:500]
            operation.save(update_fields=['billing_status', 'sunat_error_description'])

            return False

    def cleanup_old_errors(self):
        """Limpiar errores antiguos y optimizar base de datos"""
        from operations.models import Operation

        if self.verbose:
            self.stdout.write(
                self.style.MIGRATE_LABEL('\n🧹 LIMPIEZA Y OPTIMIZACIÓN...')
            )

        # Marcar como finalizados los documentos que superaron reintentos
        exceeded = Operation.objects.filter(
            billing_status='ERROR',
            retry_count__gte=F('max_retries')
        ).update(
            billing_status='ERROR_FINAL',
            updated_at=timezone.now()
        )

        if exceeded > 0 and self.verbose:
            self.stdout.write(f'  🔚 Marcados como error final: {exceeded} documentos')

    def reset_cycle_stats(self):
        """Resetear estadísticas del ciclo actual"""
        self.cycle_stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'cancellations': 0,
            'errors': []
        }

    def print_header(self):
        """Imprimir encabezado del demonio"""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'=' * 80}\n"
                f"🚀 DEMONIO DE FACTURACIÓN ELECTRÓNICA SUNAT\n"
                f"{'=' * 80}\n"
            )
        )

        config_info = [
            f"⏰ Intervalo: {self.interval} segundos ({self.interval / 3600:.1f} horas)",
            f"📦 Tamaño de lote: {self.batch_size} documentos",
            f"🔄 Máximo reintentos: {self.max_retries}",
            f"⏳ Reintentar después de: {self.retry_after} minutos",
            f"🔧 Modo: {'SIMULACIÓN' if self.dry_run else 'PRODUCCIÓN'}",
            f"🔁 Ejecución: {'ÚNICA' if self.once else 'CONTINUA'}",
            f"📊 Verbosidad: {'ALTA' if self.verbose else 'NORMAL'}"
        ]

        for info in config_info:
            self.stdout.write(f"  {info}")

        self.stdout.write(f"\n🕐 Inicio: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write(f"{'=' * 80}\n")

    def print_cycle_summary(self, cycle_num):
        """Imprimir resumen del ciclo"""
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"\n📊 RESUMEN DEL CICLO #{cycle_num}")
        )

        summary = [
            f"  📋 Procesados: {self.stats['processed']}",
            f"  ✅ Exitosos: {self.stats['success']}",
            f"  ❌ Fallidos: {self.stats['failed']}",
            f"  ⏭️ Omitidos: {self.stats['skipped']}",
            f"  🚫 Anulaciones: {self.stats['cancellations']}",
        ]

        for line in summary:
            self.stdout.write(line)

        if self.stats['errors'] and self.verbose:
            self.stdout.write(
                self.style.ERROR(f"\n  ⚠️ Errores detectados: {len(self.stats['errors'])}")
            )
            for error in self.stats['errors'][:5]:  # Mostrar máximo 5 errores
                self.stdout.write(f"    - {error.get('operation', 'N/A')}: {error['error'][:100]}")

    def print_final_summary(self):
        """Imprimir resumen final al terminar"""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'=' * 80}\n"
                f"📊 RESUMEN FINAL DE EJECUCIÓN\n"
                f"{'=' * 80}\n"
            )
        )

        total_processed = self.stats['processed']
        success_rate = (self.stats['success'] / total_processed * 100) if total_processed > 0 else 0

        summary = [
            f"⏱️ Tiempo de ejecución: {self.get_runtime()}",
            f"📋 Total procesados: {total_processed}",
            f"✅ Exitosos: {self.stats['success']} ({success_rate:.1f}%)",
            f"❌ Fallidos: {self.stats['failed']}",
            f"⏭️ Omitidos: {self.stats['skipped']}",
            f"🚫 Anulaciones: {self.stats['cancellations']}",
            f"⚠️ Total errores: {len(self.stats['errors'])}"
        ]

        for line in summary:
            self.stdout.write(f"  {line}")

        self.stdout.write(f"\n🏁 Finalizado: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write(f"{'=' * 80}\n")

    def wait_next_cycle(self):
        """Esperar hasta el siguiente ciclo mostrando cuenta regresiva"""
        next_run = timezone.now() + timedelta(seconds=self.interval)

        self.stdout.write(
            self.style.WARNING(
                f"\n⏳ Próxima ejecución: {next_run.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        # Mostrar cuenta regresiva si verbose está activo
        if self.verbose:
            for remaining in range(self.interval, 0, -60):  # Actualizar cada minuto
                if not self.running:
                    break

                if remaining >= 60:
                    mins = remaining // 60
                    self.stdout.write(
                        f"\r  ⏰ Esperando: {mins} minutos restantes...",
                        ending=''
                    )
                    self.stdout.flush()

                time.sleep(min(60, remaining))
        else:
            # Espera simple sin cuenta regresiva
            time.sleep(self.interval)

    def signal_handler(self, signum, frame):
        """Manejador de señales para detener el demonio elegantemente"""
        self.stdout.write(
            self.style.WARNING('\n\n⚠️ Señal recibida. Deteniendo demonio elegantemente...')
        )
        self.running = False

    def get_runtime(self):
        """Calcular tiempo de ejecución"""
        if hasattr(self, 'start_time'):
            runtime = timezone.now() - self.start_time
            hours = runtime.seconds // 3600
            minutes = (runtime.seconds % 3600) // 60
            return f"{runtime.days} días, {hours} horas, {minutes} minutos"
        return "N/A"

    def __enter__(self):
        """Context manager entry"""
        self.start_time = timezone.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        pass