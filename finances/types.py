import graphene
from graphene_django import DjangoObjectType

from finances.models import Payment


class PaymentType(DjangoObjectType):
    id = graphene.Int()

    class Meta:
        model = Payment
        fields = "__all__"
        interfaces = (graphene.relay.Node,)


class PaymentInput(graphene.InputObjectType):
    id = graphene.Int()
    type = graphene.String(default="I")
    payment_type = graphene.String(required=True)
    payment_method = graphene.String(required=True)
    status = graphene.String(default="C")
    notes = graphene.String()
    payment_date = graphene.String(default=0)
    total_amount = graphene.Float(default=0)
    paid_amount = graphene.Float(required=True)
    user_id = graphene.Int()
    company_id = graphene.Int()
    operation_id = graphene.Int()


class UpdatePaymentInput(graphene.InputObjectType):
    status = graphene.String()
    notes = graphene.String()
    paid_amount = graphene.Float()
