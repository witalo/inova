from datetime import datetime

import graphene
from django.db.models import Sum

from finances.models import Payment
from finances.mutations import CreatePayment, UpdatePayment, DeletePayment
from finances.types import PaymentType


class FinancesQuery(graphene.ObjectType):
    # Obtener pagos por fecha y compañía
    payments_by_date = graphene.List(
        PaymentType,
        company_id=graphene.Int(required=True),
        date=graphene.String(required=True)
    )

    # Obtener un pago por ID
    payment = graphene.Field(PaymentType, id=graphene.Int(required=True))

    # Obtener resumen financiero por fecha
    financial_summary = graphene.Field(
        graphene.Float,
        company_id=graphene.Int(required=True),
        date=graphene.String(required=True),
        summary_type=graphene.String(required=True)  # 'income', 'expense', 'balance'
    )

    @staticmethod
    def resolve_payments_by_date(self, info, company_id, date):
        try:
            # Parsear la fecha
            target_date = datetime.strptime(date, '%Y-%m-%d').date()

            # Filtrar pagos por compañía y fecha
            payments = Payment.objects.filter(
                company_id=company_id,
                payment_date__date=target_date,
                is_enabled=True
            ).select_related('user', 'company', 'operation').order_by('-payment_date')

            return payments
        except Exception as e:
            raise Exception(f"Error al obtener pagos: {str(e)}")

    @staticmethod
    def resolve_payment(self, info, id):
        try:
            return Payment.objects.get(pk=id, is_enabled=True)
        except Payment.DoesNotExist:
            raise Exception("Pago no encontrado")

    @staticmethod
    def resolve_financial_summary(self, info, company_id, date, summary_type):
        try:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()

            base_query = Payment.objects.filter(
                company_id=company_id,
                payment_date__date=target_date,
                is_enabled=True,
                status='C'  # Solo pagos cancelados
            )

            if summary_type == 'income':
                result = base_query.filter(type='I').aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0
            elif summary_type == 'expense':
                result = base_query.filter(type='E').aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0
            elif summary_type == 'balance':
                income = base_query.filter(type='I').aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0
                expense = base_query.filter(type='E').aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0
                result = float(income) - float(expense)
            else:
                raise Exception("Tipo de resumen inválido")

            return float(result)
        except Exception as e:
            raise Exception(f"Error al calcular resumen: {str(e)}")


class FinancesMutation(graphene.ObjectType):
    create_payment = CreatePayment.Field()
    update_payment = UpdatePayment.Field()
    delete_payment = DeletePayment.Field()
