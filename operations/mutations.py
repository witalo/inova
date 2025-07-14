import os
import re
from datetime import date
from decimal import Decimal
from datetime import datetime
import graphene
from django.db import transaction
from django.utils import timezone
from datetime import datetime, date, time
from finances.models import Payment
from finances.types import PaymentInput
from operations.models import Person, Serial, Operation, OperationDetail
from operations.types import PersonInput, PersonType, OperationDetailInput, OperationType
from operations.views import generate_next_number
from products.models import Product, TypeAffectation
from django.utils import timezone
import pytz

# Definir la zona horaria de Perú
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
        payments = graphene.List(PaymentInput, required=True)  # Nuevo campo

    operation = graphene.Field(OperationType)
    success = graphene.Boolean()
    message = graphene.String()

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

            # Crear la operación
            operation = Operation.objects.create(
                document_id=document_id,
                serial=serial,
                number=next_number,
                operation_type=operation_type,
                operation_status='1',  # Registrado
                operation_date=operation_date,
                emit_date=emit_date,
                emit_time=emit_time,
                person_id=kwargs.get('person_id'),
                user_id=user_id,
                company_id=company_id,
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
                    user_id=user_id,
                    operation=operation,
                    company_id=company_id,
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

            return CreateOperation(
                operation=operation,
                success=True,
                message='Operación creada exitosamente'
            )

        except Exception as e:
            transaction.set_rollback(True)
            return CreateOperation(
                operation=None,
                success=False,
                message=str(e)
            )
# class CreateOperation(graphene.Mutation):
#     class Arguments:
#         document_id = graphene.ID()
#         serial_id = graphene.ID()
#         operation_type = graphene.String(required=True)
#         operation_date = graphene.String(required=True)
#         serial = graphene.String()
#         number = graphene.Int()
#         emit_date = graphene.String(required=True)
#         emit_time = graphene.String(required=True)
#         person_id = graphene.ID()
#         user_id = graphene.ID(required=True)
#         company_id = graphene.ID(required=True)
#         currency = graphene.String(default_value='PEN')
#         global_discount_percent = graphene.Float(default_value=0)
#         global_discount = graphene.Float(default_value=0)
#         total_discount = graphene.Float(default_value=0)
#         igv_percent = graphene.Float(default_value=18)
#         igv_amount = graphene.Float(required=True)
#         total_taxable = graphene.Float(default_value=0)
#         total_unaffected = graphene.Float(default_value=0)
#         total_exempt = graphene.Float(default_value=0)
#         total_free = graphene.Float(default_value=0)
#         total_amount = graphene.Float(required=True)
#         items = graphene.List(OperationDetailInput, required=True)
#         payments = graphene.List(PaymentInput, required=True)  # Nuevo campo
#
#     operation = graphene.Field(OperationType)
#     success = graphene.Boolean()
#     message = graphene.String()
#
#     @transaction.atomic
#     def mutate(self, info, **kwargs):
#         try:
#             print('Operacion:', kwargs)
#
#             # Parsear fechas
#             operation_date = datetime.strptime(kwargs['operation_date'], '%Y-%m-%d').date()
#             emit_date = datetime.strptime(kwargs['emit_date'], '%Y-%m-%d').date()
#             emit_time = datetime.strptime(kwargs['emit_time'], '%H:%M:%S').time()
#
#             operation_type = kwargs['operation_type']
#             company_id = kwargs['company_id']
#             document_id = kwargs.get('document_id')
#             serial = None
#             next_number = None
#
#             # Lógica existente para serial y número
#             if operation_type == "E":
#                 serial = kwargs.get('serial', '')
#                 next_number = kwargs.get('number', 0)
#                 document_id = None
#                 if serial == "" or next_number == 0:
#                     serial = "E001"
#                     next_number = generate_next_number(serial, company_id, operation_type)
#             elif operation_type == "S":
#                 serial_document = Serial.objects.get(id=kwargs['serial_id'])
#                 serial = serial_document.serial
#                 next_number = generate_next_number(serial, company_id, operation_type)
#
#             user_id = kwargs['user_id']
#
#             # Crear la operación
#             operation = Operation.objects.create(
#                 document_id=document_id,
#                 serial=serial,
#                 number=next_number,
#                 operation_type=operation_type,
#                 operation_status='1',  # Registrado
#                 operation_date=operation_date,
#                 emit_date=emit_date,
#                 emit_time=emit_time,
#                 person_id=kwargs.get('person_id'),
#                 user_id=user_id,
#                 company_id=company_id,
#                 currency=kwargs['currency'],
#                 global_discount_percent=kwargs['global_discount_percent'],
#                 global_discount=kwargs['global_discount'],
#                 total_discount=kwargs['total_discount'],
#                 igv_percent=kwargs['igv_percent'],
#                 igv_amount=kwargs['igv_amount'],
#                 total_taxable=kwargs['total_taxable'],
#                 total_unaffected=kwargs['total_unaffected'],
#                 total_exempt=kwargs['total_exempt'],
#                 total_free=kwargs['total_free'],
#                 total_amount=kwargs['total_amount']
#             )
#
#             # Crear los detalles (código existente)
#             for item in kwargs['items']:
#                 product = Product.objects.get(id=item['product_id'])
#
#                 quantity = Decimal(str(item['quantity']))
#                 unit_value = Decimal(str(item['unit_value']))
#                 unit_price = Decimal(str(item['unit_price']))
#                 discount_percentage = Decimal(str(item.get('discount_percentage', 0)))
#
#                 total_value = quantity * unit_value
#                 total_discount = total_value * (discount_percentage / 100)
#                 total_value_after_discount = total_value - total_discount
#
#                 type_affectation = TypeAffectation.objects.get(code=item['type_affectation_id'])
#                 if type_affectation.code == 10:  # Gravada
#                     total_igv = total_value_after_discount * (Decimal(str(kwargs['igv_percent'])) / 100)
#                 else:
#                     total_igv = Decimal('0')
#
#                 total_amount_detail = total_value_after_discount + total_igv
#
#                 OperationDetail.objects.create(
#                     operation=operation,
#                     product=product,
#                     description=product.description,
#                     type_affectation_id=item['type_affectation_id'],
#                     quantity=quantity,
#                     unit_value=unit_value,
#                     unit_price=unit_price,
#                     discount_percentage=discount_percentage,
#                     total_discount=total_discount,
#                     total_value=total_value_after_discount,
#                     total_igv=total_igv,
#                     total_amount=total_amount_detail
#                 )
#
#                 # Actualizar stock
#                 if operation_type == 'S':
#                     product.stock -= quantity
#                     product.save()
#                 elif operation_type == 'E':
#                     product.stock += quantity
#                     product.purchase_price = unit_price
#                     product.save()
#             payment_type = 'I'
#             notes_operation = "SIN ESPECIFICAR"
#             if operation_type == 'S':
#                 payment_type = 'I'
#                 notes_operation = "SALIDA DE PRODUCTOS"
#             elif operation_type == 'E':
#                 payment_type = 'E'
#                 notes_operation = "ENTRADA DE PRODUCTOS"
#             # NUEVO: Crear los pagos
#             payments = kwargs.get('payments', [])
#             total_paid = Decimal('0')
#
#             # Si no hay pagos o is_payment está deshabilitado, crear pago automático
#             if not payments:
#                 # Usar emit_date con la hora actual (no time.min)
#                 current_time = timezone.now().time()
#                 payment_datetime = timezone.make_aware(
#                     datetime.combine(emit_date, current_time)
#                 )
#
#                 # Si no tiene pagos habilitados, crear pago automático al contado/efectivo
#                 Payment.objects.create(
#                     payment_type='CN',  # Contado
#                     payment_method='E',  # Efectivo
#                     status='C',  # Cancelado
#                     type=payment_type,
#                     notes=notes_operation,
#                     user_id=user_id,
#                     operation=operation,
#                     company_id=company_id,
#                     payment_date=payment_datetime,
#                     total_amount=operation.total_amount,
#                     paid_amount=operation.total_amount
#                 )
#                 total_paid = operation.total_amount
#             else:
#                 # Crear los pagos enviados desde el frontend
#                 for payment_data in payments:
#                     # Parsear la fecha y convertirla a datetime con timezone
#                     # Ahora (fecha y hora completa)
#                     payment_datetime = timezone.make_aware(
#                         datetime.strptime(payment_data['payment_date'], '%Y-%m-%d %H:%M:%S')
#                     )
#                     paid_amount = Decimal(str(payment_data['paid_amount']))
#                     # Versión mejorada con validación de notes
#                     notes = payment_data.get('notes', '')
#                     if not notes:  # Esto cubre None, '', '   ', etc.
#                         notes = notes_operation
#                     elif len(notes.strip()) <= 4:  # Si quieres descartar textos muy cortos
#                         notes = f"{notes_operation} - {notes}"
#
#                     Payment.objects.create(
#                         payment_type=payment_data['payment_type'],
#                         payment_method=payment_data['payment_method'],
#                         status=payment_data.get('status', 'C'),
#                         type=payment_type,
#                         notes=notes,
#                         user_id=kwargs['user_id'],
#                         operation=operation,
#                         company_id=company_id,
#                         payment_date=payment_datetime,  # Usar datetime con timezone
#                         total_amount=operation.total_amount,
#                         paid_amount=paid_amount
#                     )
#                     total_paid += paid_amount
#
#             # Convertir ambos valores a Decimal
#             total_paid_decimal = Decimal(str(total_paid))
#             operation_total_decimal = Decimal(str(operation.total_amount))
#
#             if abs(total_paid_decimal - operation_total_decimal) > Decimal('0.01'):
#                 raise Exception(
#                     f'El total pagado ({total_paid}) no coincide con el total de la operación ({operation.total_amount})')
#
#             return CreateOperation(
#                 operation=operation,
#                 success=True,
#                 message='Operación creada exitosamente'
#             )
#
#         except Exception as e:
#             transaction.set_rollback(True)
#             return CreateOperation(
#                 operation=None,
#                 success=False,
#                 message=str(e)
#             )


class CancelOperation(graphene.Mutation):
    class Arguments:
        operation_id = graphene.ID(required=True)
        reason = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    @transaction.atomic
    def mutate(self, info, operation_id, reason):
        try:
            operation = Operation.objects.get(id=operation_id)

            # Validar que se pueda anular
            if operation.operation_status not in ['1', '2']:
                return CancelOperation(
                    success=False,
                    message='La operación no puede ser anulada en su estado actual'
                )

            # Cambiar estado
            operation.operation_status = '3'  # Pendiente de baja
            operation.sunat_description_low = reason
            operation.low_date = date.today()
            operation.save()

            # Revertir stock si es salida
            if operation.operation_type == 'S':
                for detail in operation.operationdetail_set.all():
                    if detail.product:
                        detail.product.stock += detail.quantity
                        detail.product.save()

            return CancelOperation(
                success=True,
                message='Operación anulada exitosamente'
            )

        except Exception as e:
            transaction.set_rollback(True)
            return CancelOperation(
                success=False,
                message=str(e)
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
