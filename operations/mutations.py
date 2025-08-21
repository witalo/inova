import os
import re
from datetime import datetime, date, time
from finances.models import Payment
from finances.types import PaymentInput
from inova import settings
from operations.models import Person, Serial, Operation, OperationDetail
from operations.types import PersonInput, PersonType, OperationDetailInput, OperationType
from operations.views import generate_next_number, get_peru_date
from products.models import Product, TypeAffectation
from django.utils import timezone
import graphene
from django.db import transaction
from decimal import Decimal
import pytz
import logging
# Configurar logger
from users.models import Company, User

logger = logging.getLogger('operations.tasks')
peru_tz = pytz.timezone('America/Lima')


class PersonMutation(graphene.Mutation):
    class Arguments:
        input = PersonInput(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    person = graphene.Field(PersonType)
    errors = graphene.JSONString()

    @staticmethod
    def mutate(root, info, input):
        errors = {}
        person = None

        try:
            # === Validaciones ===
            # Validar tipo de documento
            if input.person_type not in dict(Person.PERSON_TYPE_CHOICES).keys():
                errors["person_type"] = f"Tipo inválido. Opciones: {dict(Person.PERSON_TYPE_CHOICES)}"

            # Validar formato del número según tipo
            if input.person_type == '1' and not input.person_number.isdigit() or len(input.person_number) != 8:
                errors["person_number"] = "DNI requiere 8 dígitos numéricos"
            elif input.person_type == '6' and not input.person_number.isdigit() or len(input.person_number) != 11:
                errors["person_number"] = "RUC requiere 11 dígitos numéricos"

            # Validar email si existe
            if input.email and not re.match(r"[^@]+@[^@]+\.[^@]+", input.email):
                errors["email"] = "Formato de email inválido"

            if errors:
                raise ValueError("Errores de validación")

            # === Obtener o crear persona ===
            if input.id:
                try:
                    person = Person.objects.get(pk=input.id)
                except Person.DoesNotExist:
                    raise ValueError("Persona no encontrada")
            else:
                if Person.objects.filter(person_number=input.person_number).exists():
                    raise ValueError("Ya existe una persona con este documento")
                person = Person()

            # === Actualizar campos ===
            person.person_type = input.person_type
            person.person_number = input.person_number
            person.full_name = input.full_name.strip()
            person.is_customer = input.is_customer if input.is_customer is not None else False
            person.is_supplier = input.is_supplier if input.is_supplier is not None else False
            person.address = input.address.strip() if input.address else None
            person.phone = input.phone.strip() if input.phone else None
            person.email = input.email.lower().strip() if input.email else None

            # === Guardar ===
            person.full_clean()  # Validación de modelo Django
            person.save()

            return PersonMutation(
                success=True,
                message="Persona guardada exitosamente",
                person=person,
                errors=None
            )

        except Exception as e:
            return PersonMutation(
                success=False,
                message=str(e),
                person=person,
                errors=errors if errors else {"general": str(e)}
            )


class CreateOperation(graphene.Mutation):
    class Arguments:
        document_id = graphene.ID()
        serial_id = graphene.ID()
        operation_type = graphene.String(required=True)
        operation_date = graphene.String(required=True)
        serial = graphene.String()
        number = graphene.Int()
        emit_date = graphene.String(required=True)
        emit_time = graphene.String(required=True)
        person_id = graphene.ID()
        user_id = graphene.ID(required=True)
        company_id = graphene.ID(required=True)
        currency = graphene.String(default_value='PEN')
        global_discount_percent = graphene.Float(default_value=0)
        global_discount = graphene.Float(default_value=0)
        total_discount = graphene.Float(default_value=0)
        igv_percent = graphene.Float(default_value=18)
        igv_amount = graphene.Float(required=True)
        total_taxable = graphene.Float(default_value=0)
        total_unaffected = graphene.Float(default_value=0)
        total_exempt = graphene.Float(default_value=0)
        total_free = graphene.Float(default_value=0)
        total_amount = graphene.Float(required=True)
        items = graphene.List(OperationDetailInput, required=True)
        payments = graphene.List(PaymentInput, required=True)
        # Nuevos argumentos para facturación
        auto_billing = graphene.Boolean(default_value=True)  # Facturar automáticamente
        send_to_sunat = graphene.Boolean(default_value=True)  # Enviar a SUNAT

    operation = graphene.Field(OperationType)
    success = graphene.Boolean()
    message = graphene.String()
    task_id = graphene.String()  # ID de la tarea de Celery
    billing_mode = graphene.String()

    @transaction.atomic
    def mutate(self, info, **kwargs):
        try:
            print('Operacion:', kwargs)
            # Parsear fechas
            operation_date = datetime.strptime(kwargs['operation_date'], '%Y-%m-%d').date()
            emit_date = datetime.strptime(kwargs['emit_date'], '%Y-%m-%d').date()
            emit_time = datetime.strptime(kwargs['emit_time'], '%H:%M:%S').time()

            operation_type = kwargs['operation_type']
            company_id = kwargs['company_id']
            company = Company.objects.get(id=company_id)
            document_id = kwargs.get('document_id')
            serial = None
            next_number = None

            # Lógica existente para serial y número
            if operation_type == "E":
                serial = kwargs.get('serial', '')
                next_number = kwargs.get('number', 0)
                document_id = None
                if serial == "" or next_number == 0:
                    serial = "E001"
                    next_number = generate_next_number(serial, company_id, operation_type)
            elif operation_type == "S":
                serial_document = Serial.objects.get(id=kwargs['serial_id'])
                serial = serial_document.serial
                next_number = generate_next_number(serial, company_id, operation_type)

            user_id = kwargs['user_id']
            user = User.objects.get(id=user_id)

            # Crear la operación
            operation = Operation.objects.create(
                document_id=document_id,
                serial=serial,
                number=next_number,
                operation_type=operation_type,
                billing_status='REGISTER',  # Registrado
                operation_date=operation_date,
                emit_date=emit_date,
                emit_time=emit_time,
                person_id=kwargs.get('person_id'),
                user=user,
                company=company,
                currency=kwargs['currency'],
                global_discount_percent=kwargs['global_discount_percent'],
                global_discount=kwargs['global_discount'],
                total_discount=kwargs['total_discount'],
                igv_percent=kwargs['igv_percent'],
                igv_amount=kwargs['igv_amount'],
                total_taxable=kwargs['total_taxable'],
                total_unaffected=kwargs['total_unaffected'],
                total_exempt=kwargs['total_exempt'],
                total_free=kwargs['total_free'],
                total_amount=kwargs['total_amount']
            )

            # Crear los detalles (código existente)
            for item in kwargs['items']:
                product = Product.objects.get(id=item['product_id'])

                quantity = Decimal(str(item['quantity']))
                unit_value = Decimal(str(item['unit_value']))
                unit_price = Decimal(str(item['unit_price']))
                discount_percentage = Decimal(str(item.get('discount_percentage', 0)))

                total_value = quantity * unit_value
                total_discount = total_value * (discount_percentage / 100)
                total_value_after_discount = total_value - total_discount

                type_affectation = TypeAffectation.objects.get(code=item['type_affectation_id'])
                if type_affectation.code == 10:  # Gravada
                    total_igv = total_value_after_discount * (Decimal(str(kwargs['igv_percent'])) / 100)
                else:
                    total_igv = Decimal('0')

                total_amount_detail = total_value_after_discount + total_igv

                OperationDetail.objects.create(
                    operation=operation,
                    product=product,
                    description=product.description,
                    type_affectation_id=item['type_affectation_id'],
                    quantity=quantity,
                    unit_value=unit_value,
                    unit_price=unit_price,
                    discount_percentage=discount_percentage,
                    total_discount=total_discount,
                    total_value=total_value_after_discount,
                    total_igv=total_igv,
                    total_amount=total_amount_detail
                )

                # Actualizar stock
                if operation_type == 'S':
                    product.stock -= quantity
                    product.save()
                elif operation_type == 'E':
                    product.stock += quantity
                    product.purchase_price = unit_price
                    product.save()
            payment_type = 'I'
            notes_operation = "SIN ESPECIFICAR"
            if operation_type == 'S':
                payment_type = 'I'
                notes_operation = "SALIDA DE PRODUCTOS"
            elif operation_type == 'E':
                payment_type = 'E'
                notes_operation = "ENTRADA DE PRODUCTOS"
            # NUEVO: Crear los pagos
            payments = kwargs.get('payments', [])
            total_paid = Decimal('0')

            # Si no hay pagos o is_payment está deshabilitado, crear pago automático
            if not payments:
                # ✅ CORREGIDO: Usar emit_date con la hora actual en zona horaria de Perú
                current_time_peru = timezone.now().astimezone(peru_tz).time()
                payment_datetime = timezone.make_aware(
                    datetime.combine(emit_date, current_time_peru),
                    timezone=peru_tz
                )

                # Si no tiene pagos habilitados, crear pago automático al contado/efectivo
                Payment.objects.create(
                    payment_type='CN',  # Contado
                    payment_method='E',  # Efectivo
                    status='C',  # Cancelado
                    type=payment_type,
                    notes=notes_operation,
                    user=user,
                    operation=operation,
                    company=company,
                    payment_date=payment_datetime,
                    total_amount=operation.total_amount,
                    paid_amount=operation.total_amount
                )
                total_paid = operation.total_amount
            else:
                # Crear los pagos enviados desde el frontend
                for payment_data in payments:
                    # ✅ CORREGIDO: Parsear la fecha y convertirla a datetime con timezone de Perú
                    naive_datetime = datetime.strptime(payment_data['payment_date'], '%Y-%m-%d %H:%M:%S')
                    payment_datetime = timezone.make_aware(naive_datetime, timezone=peru_tz)

                    paid_amount = Decimal(str(payment_data['paid_amount']))
                    # Versión mejorada con validación de notes
                    notes = payment_data.get('notes', '')
                    if not notes:  # Esto cubre None, '', '   ', etc.
                        notes = notes_operation
                    elif len(notes.strip()) <= 4:  # Si quieres descartar textos muy cortos
                        notes = f"{notes_operation} - {notes}"

                    Payment.objects.create(
                        payment_type=payment_data['payment_type'],
                        payment_method=payment_data['payment_method'],
                        status=payment_data.get('status', 'C'),
                        type=payment_type,
                        notes=notes,
                        user_id=kwargs['user_id'],
                        operation=operation,
                        company_id=company_id,
                        payment_date=payment_datetime,  # Usar datetime con timezone
                        total_amount=operation.total_amount,
                        paid_amount=paid_amount
                    )
                    total_paid += paid_amount

            # Convertir ambos valores a Decimal
            total_paid_decimal = Decimal(str(total_paid))
            operation_total_decimal = Decimal(str(operation.total_amount))

            if abs(total_paid_decimal - operation_total_decimal) > Decimal('0.01'):
                raise Exception(
                    f'El total pagado ({total_paid}) no coincide con el total de la operación ({operation.total_amount})')
            # ==============================================
            # SECCIÓN DE FACTURACIÓN INTELIGENTE
            # ==============================================

            auto_billing = kwargs.get('auto_billing', True)
            task_id = None

            # Verificar si necesita facturación
            if auto_billing and operation_type == 'S' and company.is_billing:
                if operation.document and operation.document.code in ['01', '03', '07', '08']:
                    # Marcar como pendiente
                    operation.billing_status = 'PENDING'
                    operation.save()

                    try:
                        from operations.tasks import process_electronic_billing_task

                        # SOLO ENCOLAR - NO VERIFICAR NADA MÁS
                        result = process_electronic_billing_task.delay(operation.id)
                        task_id = str(result.id) if result else None

                        print(f"✅ Tarea encolada: {task_id}")
                        message = f'Operación creada. Facturación en proceso (Task: {task_id})'
                    except Exception as e:
                        print(f"❌ Error: {str(e)}")
                        message = 'Operación creada. Facturación pendiente'
                else:
                    message = 'Operación creada exitosamente'
            else:
                message = 'Operación creada exitosamente'

            return CreateOperation(
                operation=operation,
                success=True,
                message=message,
                task_id=task_id
            )

        except Exception as e:
            transaction.set_rollback(True)
            logger.error(f"Error creando operación: {str(e)}", exc_info=True)
            return CreateOperation(
                operation=None,
                success=False,
                message=str(e),
                task_id=None,
                billing_mode='ERROR'
            )
            # auto_billing = kwargs.get('auto_billing', True)
            # task_id = None
            #
            # if auto_billing and operation_type == 'S' and company.is_billing:
            #     # Solo facturar ventas (salidas)
            #     if operation.document and operation.document.code in ['01', '03', '07', '08']:
            #         try:
            #             # IMPORTANTE: Importar y usar Celery task
            #             from operations.tasks import process_electronic_billing_task
            #
            #             # Lanzar tarea asíncrona
            #             task = process_electronic_billing_task.delay(operation.id)
            #             task_id = str(task.id)
            #
            #             logger.info(
            #                 f"Tarea de facturación lanzada - Task ID: {task_id} para operación {operation.id}")
            #
            #             # Actualizar estado a pendiente
            #             operation.billing_status = 'PENDING'
            #             operation.save()
            #
            #             message = f'Operación creada exitosamente. Facturación en proceso (Task ID: {task_id})'
            #
            #         except ImportError as e:
            #             # Si Celery no está disponible, intentar ejecutar sincrónicamente
            #             logger.warning(f"⚠️ Celery no disponible, ejecutando sincrónicamente: {str(e)}")
            #
            #             try:
            #                 from operations.services.billing_service import BillingService
            #
            #                 operation.billing_status = 'PROCESSING'
            #                 operation.save()
            #
            #                 billing_service = BillingService(operation.id)
            #                 success = billing_service.process_electronic_billing()
            #
            #                 if success:
            #                     message = 'Operación creada y facturada exitosamente.'
            #                 else:
            #                     message = 'Operación creada. Verificar estado de facturación.'
            #
            #             except Exception as billing_error:
            #                 operation.billing_status = 'ERROR'
            #                 operation.sunat_error_description = str(billing_error)[:500]
            #                 operation.save()
            #                 message = f'Operación creada. Error en facturación: {str(billing_error)[:100]}'
            #
            #         except Exception as e:
            #             logger.error(f"❌ Error lanzando tarea de facturación: {str(e)}")
            #             operation.billing_status = 'ERROR'
            #             operation.sunat_error_description = str(e)[:500]
            #             operation.save()
            #             message = f'Operación creada. Error iniciando facturación: {str(e)[:100]}'
            #     else:
            #         message = 'Operación creada exitosamente. No requiere facturación electrónica.'
            # else:
            #     message = 'Operación creada exitosamente.'

            return CreateOperation(
                operation=operation,
                success=True,
                message=message,
                task_id=task_id
            )
            # # NUEVO CÓDIGO - Ejecutar facturación directamente
            # if auto_billing and operation_type == 'S' and company.is_billing:
            #     # Solo facturar ventas (salidas)
            #     if operation.document and operation.document.code in ['01', '03', '07', '08']:
            #         # NO USAR CELERY - Ejecutar directamente
            #         try:
            #             from operations.services.billing_service import BillingService
            #
            #             print(f" Procesando facturación directamente para operación {operation.id}...")
            #             logger.info(f" Procesando facturación directamente para operación {operation.id}")
            #
            #             # Actualizar estado
            #             operation.billing_status = 'PROCESSING'
            #             operation.save()
            #
            #             # Procesar facturación
            #             billing_service = BillingService(operation.id)
            #             success = billing_service.process_electronic_billing()
            #
            #             if success:
            #                 print(f" Facturación completada para operación {operation.id}")
            #                 message = 'Operación creada y facturada exitosamente.'
            #             else:
            #                 print(f" Facturación completada con errores para operación {operation.id}")
            #                 message = 'Operación creada. Verificar estado de facturación.'
            #
            #         except Exception as e:
            #             error_msg = str(e)
            #             print(f" Error en facturación: {error_msg}")
            #             logger.error(f" Error en facturación para operación {operation.id}: {error_msg}",
            #                          exc_info=True)
            #
            #             # Guardar error
            #             operation.billing_status = 'ERROR'
            #             operation.sunat_error_description = error_msg[:500]  # Limitar longitud
            #             operation.save()
            #
            #             message = f'Operación creada. Error en facturación: {error_msg[:100]}'
            #     else:
            #         message = 'Operación creada exitosamente. No requiere facturación electrónica.'
            # else:
            #     message = 'Operación creada exitosamente.'
            #
            # return CreateOperation(
            #     operation=operation,
            #     success=True,
            #     message=message
            # )

        except Exception as e:
            transaction.set_rollback(True)
            logger.error(f"Error creando operación: {str(e)}", exc_info=True)
            return CreateOperation(
                operation=None,
                success=False,
                message=str(e),
                task_id=None
            )


class CancelOperation(graphene.Mutation):
    class Arguments:
        operation_id = graphene.ID(required=True)
        cancellation_reason = graphene.String(default_value='01')

    success = graphene.Boolean()
    message = graphene.String()
    operation = graphene.Field(OperationType)
    task_id = graphene.String()
    cancellation_mode = graphene.String()

    def mutate(self, info, operation_id, cancellation_reason='01'):
        try:
            from operations.models import Operation

            operation = Operation.objects.get(id=operation_id)

            # Buscar la descripción desde los choices del modelo
            reason_dict = dict(Operation._meta.get_field("cancellation_reason").choices)
            cancellation_description = reason_dict.get(cancellation_reason, "Motivo desconocido")
            # Guardar datos de anulación
            operation.cancellation_reason = cancellation_reason
            operation.cancellation_description = cancellation_description
            operation.cancellation_date = get_peru_date()
            task_id = None
            message = "-"
            if operation.billing_status == "REGISTER":
                operation.billing_status = 'CANCELLED'
                operation.save()
                message = f'Operacion anulada con exito'
            elif operation.billing_status in ['ACCEPTED', 'ACCEPTED_WITH_OBSERVATIONS']:
                operation.billing_status = 'PROCESSING_CANCELLATION'
                operation.save()
                try:
                    from operations.tasks import cancel_document_task

                    # SOLO ENCOLAR - SIMPLE
                    result = cancel_document_task.delay(
                        operation_id,
                        cancellation_reason,
                        cancellation_description
                    )
                    task_id = str(result.id) if result else None

                    print(f"✅ Anulación encolada: {task_id}")
                    message = f'Proceso de anulación iniciado (Task: {task_id})'

                except Exception as e:
                    print(f"❌ Error: {str(e)}")
                    message = 'Anulación pendiente de procesamiento'
            else:
                return CancelOperation(
                    success=False,
                    message=f'Solo se pueden anular documentos aceptados. Estado actual: {operation.billing_status}',
                    operation=operation,
                    task_id=task_id
                )
            return CancelOperation(
                success=True,
                message=message,
                operation=operation,
                task_id=task_id
            )
        except Operation.DoesNotExist:
            return CancelOperation(
                success=False,
                message='Operación no encontrada',
                operation=None,
                task_id=None
            )
        except Exception as e:
            return CancelOperation(
                success=False,
                message=str(e),
                operation=None,
                task_id=None
            )


class CheckTaskStatus(graphene.Mutation):
    """Mutación para verificar el estado de una tarea de Celery"""

    class Arguments:
        task_id = graphene.String(required=True)

    success = graphene.Boolean()
    status = graphene.String()
    result = graphene.String()
    message = graphene.String()

    def mutate(self, info, task_id):
        try:
            from celery.result import AsyncResult

            result = AsyncResult(task_id)

            status_map = {
                'PENDING': 'Pendiente',
                'STARTED': 'Iniciado',
                'RETRY': 'Reintentando',
                'SUCCESS': 'Completado',
                'FAILURE': 'Error'
            }

            status = status_map.get(result.state, result.state)

            # Obtener resultado si está disponible
            task_result = None
            if result.ready():
                try:
                    task_result = str(result.result)
                except:
                    task_result = 'Resultado no disponible'

            return CheckTaskStatus(
                success=True,
                status=status,
                result=task_result,
                message=f'Estado de tarea: {status}'
            )

        except Exception as e:
            return CheckTaskStatus(
                success=False,
                status='ERROR',
                result=None,
                message=f'Error verificando tarea: {str(e)}'
            )


class ResendOperationToBilling(graphene.Mutation):
    class Arguments:
        operation_id = graphene.ID(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    operation = graphene.Field(OperationType)

    def mutate(self, info, operation_id):
        try:
            from operations.models import Operation
            from operations.tasks import process_electronic_billing_task

            operation = Operation.objects.get(id=operation_id)

            # Validar que se puede reenviar
            if operation.billing_status in ['ACCEPTED', 'CANCELLED']:
                return ResendOperationToBilling(
                    success=False,
                    message='No se puede reenviar un documento ya procesado o anulado',
                    operation=operation
                )

            # Resetear contador de reintentos si es necesario
            if operation.retry_count >= operation.max_retries:
                operation.retry_count = 0
                operation.save()

            # Lanzar tarea de facturación
            process_electronic_billing_task.delay(operation_id)

            return ResendOperationToBilling(
                success=True,
                message='Documento reenviado para facturación',
                operation=operation
            )

        except Operation.DoesNotExist:
            return ResendOperationToBilling(
                success=False,
                message='Operación no encontrada',
                operation=None
            )
        except Exception as e:
            return ResendOperationToBilling(
                success=False,
                message=str(e),
                operation=None
            )


class CreatePerson(graphene.Mutation):
    class Arguments:
        person_type = graphene.String(required=True)
        document = graphene.String(required=True)
        full_name = graphene.String(required=True)
        is_customer = graphene.Boolean(default_value=True)
        is_supplier = graphene.Boolean(default_value=False)
        address = graphene.String()
        phone = graphene.String()
        email = graphene.String()

    person = graphene.Field(PersonType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, **kwargs):
        try:
            # Validar documento único
            if Person.objects.filter(document=kwargs['document']).exists():
                return CreatePerson(
                    person=None,
                    success=False,
                    message='Ya existe una persona con este documento'
                )

            person = Person.objects.create(**kwargs)

            return CreatePerson(
                person=person,
                success=True,
                message='Persona creada exitosamente'
            )

        except Exception as e:
            return CreatePerson(
                person=None,
                success=False,
                message=str(e)
            )
