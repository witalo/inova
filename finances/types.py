import graphene
from graphene_django import DjangoObjectType

from finances.models import Payment, Quota, Cash


class CashType(DjangoObjectType):
    account_type_display = graphene.String()

    class Meta:
        model = Cash
        fields = "__all__"
        interfaces = (graphene.relay.Node,)

    def resolve_account_type_display(self, info):
        return self.get_account_type_display()


class PaymentType(DjangoObjectType):
    way_pay_display = graphene.String()

    class Meta:
        model = Payment
        fields = "__all__"
        interfaces = (graphene.relay.Node,)

    def resolve_way_pay_display(self, info):
        return self.get_way_pay_display()


class QuotaType(DjangoObjectType):
    class Meta:
        model = Quota
        fields = "__all__"
        interfaces = (graphene.relay.Node,)


class CashInput(graphene.InputObjectType):
    id = graphene.ID(description="Omitir para creación")
    name = graphene.String(required=True)
    account_number = graphene.String()
    account_type = graphene.String(required=True, description="C (Caja) | B (Banco)")
    is_enabled = graphene.Boolean(default=True)


class PaymentInput(graphene.InputObjectType):
    id = graphene.ID(description="Omitir para creación")
    cash_id = graphene.ID()
    user_id = graphene.ID(required=True)
    operation_id = graphene.ID()
    transaction_date = graphene.Date(required=True)
    way_pay = graphene.Int(required=True, description="1-9 según WAY_PAY_CHOICES")
    bank_operation_code = graphene.String()
    description = graphene.String()
    total = graphene.Decimal(required=True)
    is_validated = graphene.Boolean(default=False)


class QuotaInput(graphene.InputObjectType):
    id = graphene.ID(description="Omitir para creación")
    payment_date = graphene.Date(required=True)
    number = graphene.Int(required=True)
    total = graphene.Decimal(required=True)
    payment_id = graphene.ID(required=True)