import decimal
from datetime import datetime

import graphene
from django.db import transaction
from django.db.models import Sum

from finances.models import Payment
from finances.types import PaymentInput, PaymentType, UpdatePaymentInput
from operations.models import Operation
from users.models import User


class CreatePayment(graphene.Mutation):
    class Arguments:
        input = PaymentInput(required=True)

    payment = graphene.Field(PaymentType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, input):
        try:
            # Parsear fecha
            payment_date = datetime.strptime(input.payment_date, '%Y-%m-%d')

            # Crear pago
            payment = Payment.objects.create(
                type=input.type,
                payment_type=input.payment_type,
                payment_method=input.payment_method,
                status=input.status,
                notes=input.notes,
                payment_date=payment_date,
                total_amount=decimal.Decimal(input.total_amount),
                paid_amount=decimal.Decimal(input.paid_amount),
                user_id=input.user_id,
                company_id=input.company_id,
                operation_id=input.operation_id if hasattr(input, 'operation_id') else None
            )

            return CreatePayment(
                payment=payment,
                success=True,
                message="Pago creado exitosamente"
            )
        except Exception as e:
            return CreatePayment(
                payment=None,
                success=False,
                message=str(e)
            )


class UpdatePayment(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)
        input = UpdatePaymentInput(required=True)

    payment = graphene.Field(PaymentType)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id, input):
        try:
            # Validar permisos
            user = info.context.user
            if not user.is_authenticated:
                raise Exception("Usuario no autenticado")

            # Obtener pago
            payment = Payment.objects.get(pk=id, is_enabled=True)

            # Actualizar campos si se proporcionan
            if input.status is not None:
                payment.status = input.status
            if input.notes is not None:
                payment.notes = input.notes
            if input.paid_amount is not None:
                payment.paid_amount = input.paid_amount

                # Si se paga el total, cambiar estado a cancelado
                if payment.paid_amount >= payment.total_amount:
                    payment.status = 'C'

            payment.save()

            return UpdatePayment(
                payment=payment,
                success=True,
                message="Pago actualizado exitosamente"
            )
        except Payment.DoesNotExist:
            return UpdatePayment(
                payment=None,
                success=False,
                message="Pago no encontrado"
            )
        except Exception as e:
            return UpdatePayment(
                payment=None,
                success=False,
                message=str(e)
            )


class DeletePayment(graphene.Mutation):
    class Arguments:
        id = graphene.Int(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, id):
        try:
            # Validar permisos
            user = info.context.user
            if not user.is_authenticated:
                raise Exception("Usuario no autenticado")

            # Soft delete
            payment = Payment.objects.get(pk=id, is_enabled=True)
            payment.is_enabled = False
            payment.save()

            return DeletePayment(
                success=True,
                message="Pago eliminado exitosamente"
            )
        except Payment.DoesNotExist:
            return DeletePayment(
                success=False,
                message="Pago no encontrado"
            )
        except Exception as e:
            return DeletePayment(
                success=False,
                message=str(e)
            )


