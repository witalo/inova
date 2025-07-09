import graphene

from finances.models import Payment
from finances.mutations import PaymentMutation
from finances.types import PaymentType


class FinancesQuery(graphene.ObjectType):
    payments_by_date = graphene.List(
        PaymentType,
        start_date=graphene.Date(required=True),
        end_date=graphene.Date(required=True),
        company_id=graphene.ID(required=True),
    )

    @staticmethod
    def resolve_payments_by_date(self, info, start_date, end_date, company_id):
        return Payment.objects.filter(
            payment_date__range=[start_date, end_date],
            company_id=company_id
        ).order_by('-payment_date')


class FinancesMutation(graphene.ObjectType):
    payment_mutation = PaymentMutation.Field()
