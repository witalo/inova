import graphene

from finances.models import Cash, Payment
from finances.mutations import CashMutation, PaymentMutation, QuotaMutation
from finances.types import CashType, PaymentType


class FinancesQuery(graphene.ObjectType):
    all_cashes = graphene.List(CashType, is_enabled=graphene.Boolean())
    cash_by_id = graphene.Field(CashType, id=graphene.ID(required=True))
    payments_by_date = graphene.List(
        PaymentType,
        start_date=graphene.Date(required=True),
        end_date=graphene.Date(required=True)
    )

    @staticmethod
    def resolve_all_cashes(self, info, is_enabled=None, **kwargs):
        queryset = Cash.objects.all()
        if is_enabled is not None:
            queryset = queryset.filter(is_enabled=is_enabled)
        return queryset

    @staticmethod
    def resolve_cash_by_id(self, info, id):
        return Cash.objects.get(pk=id)

    @staticmethod
    def resolve_payments_by_date(self, info, start_date, end_date):
        return Payment.objects.filter(
            transaction_date__range=[start_date, end_date]
        ).order_by('-transaction_date')


class FinancesMutation(graphene.ObjectType):
    cash_mutation = CashMutation.Field()
    payment_mutation = PaymentMutation.Field()
    quota_mutation = QuotaMutation.Field()
