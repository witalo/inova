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
