import graphene
from graphene_django import DjangoObjectType

from finances.models import Payment


class PaymentType(DjangoObjectType):
    class Meta:
        model = Payment
        fields = "__all__"
        interfaces = (graphene.relay.Node,)


class PaymentInput(graphene.InputObjectType):
    payment_type = graphene.String(required=True)
    payment_method = graphene.String(required=True)
    status = graphene.String(default_value='C')
    notes = graphene.String()
    payment_date = graphene.String(required=True)
    paid_amount = graphene.Float(required=True)
