import graphene
from django.db import transaction
from django.db.models import Sum

from finances.models import Payment
from finances.types import PaymentInput, PaymentType
from operations.models import Operation
from users.models import User


class PaymentMutation(graphene.Mutation):
    class Arguments:
        input = PaymentInput(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    payment = graphene.Field(PaymentType)

    @staticmethod
    def mutate(root, info, input):
        try:
            input = input
        except Exception as e:
            return PaymentMutation(
                success=False,
                message=str(e),
                payment=None
            )


