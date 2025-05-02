import graphene
from django.db import transaction
from django.db.models import Sum

from finances.models import Quota, Cash, Payment
from finances.types import CashInput, CashType, PaymentInput, PaymentType, QuotaInput, QuotaType
from operations.models import Operation
from users.models import User


class CashMutation(graphene.Mutation):
    class Arguments:
        input = CashInput(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    cash = graphene.Field(CashType)

    @staticmethod
    def mutate(root, info, input):
        try:
            with transaction.atomic():
                # Validación de tipo de cuenta
                if input.account_type not in dict(Cash.ACCOUNT_TYPE_CHOICES):
                    raise ValueError("Tipo de cuenta inválido. Use C (Caja) o B (Banco)")

                if input.id:
                    cash = Cash.objects.select_for_update().get(pk=input.id)
                    if Cash.objects.exclude(pk=input.id).filter(name=input.name).exists():
                        raise ValueError("Nombre ya existe en otra cuenta")
                else:
                    if Cash.objects.filter(name=input.name).exists():
                        raise ValueError("Nombre ya existe")
                    cash = Cash()

                cash.name = input.name
                cash.account_number = input.account_number
                cash.account_type = input.account_type
                cash.is_enabled = input.is_enabled
                cash.save()

                return CashMutation(
                    success=True,
                    message="Cuenta guardada exitosamente",
                    cash=cash
                )
        except Exception as e:
            return CashMutation(
                success=False,
                message=str(e),
                cash=None
            )


class PaymentMutation(graphene.Mutation):
    class Arguments:
        input = PaymentInput(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    payment = graphene.Field(PaymentType)

    @staticmethod
    def mutate(root, info, input):
        try:
            with transaction.atomic():
                # Validar método de pago
                if input.way_pay not in dict(Payment.WAY_PAY_CHOICES):
                    raise ValueError("Método de pago inválido")

                payment = Payment.objects.get(pk=input.id) if input.id else Payment()

                # Asignar relaciones
                payment.cash = Cash.objects.get(pk=input.cash_id) if input.cash_id else None
                payment.user = User.objects.get(pk=input.user_id)
                payment.operation = Operation.objects.get(pk=input.operation_id) if input.operation_id else None

                # Actualizar campos
                payment.transaction_date = input.transaction_date
                payment.way_pay = input.way_pay
                payment.bank_operation_code = input.bank_operation_code
                payment.description = input.description
                payment.total = input.total
                payment.remaining_total = input.total  # Reset al monto original
                payment.is_validated = input.is_validated

                payment.save()
                return PaymentMutation(
                    success=True,
                    message="Pago registrado exitosamente",
                    payment=payment
                )
        except Exception as e:
            return PaymentMutation(
                success=False,
                message=str(e),
                payment=None
            )


class QuotaMutation(graphene.Mutation):
    class Arguments:
        input = QuotaInput(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    quota = graphene.Field(QuotaType)

    @staticmethod
    def mutate(root, info, input):
        try:
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(pk=input.payment_id)

                quota = Quota.objects.get(pk=input.id) if input.id else Quota()
                quota.payment_date = input.payment_date
                quota.number = input.number
                quota.total = input.total
                quota.payment = payment
                quota.save()

                # Actualizar saldo pendiente del pago
                total_cuotas = payment.quota_set.aggregate(
                    Sum('total')
                )['total__sum'] or 0
                payment.remaining_total = payment.total - total_cuotas
                payment.save()

                return QuotaMutation(
                    success=True,
                    message="Cuota registrada exitosamente",
                    quota=quota
                )
        except Exception as e:
            return QuotaMutation(
                success=False,
                message=str(e),
                quota=None
            )
