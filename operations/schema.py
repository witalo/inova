from datetime import datetime

import graphene

from operations.models import Person
from operations.mutations import PersonMutation
from operations.types import PersonType


class OperationsQuery(graphene.ObjectType):
    clients = graphene.List(PersonType)
    suppliers = graphene.List(PersonType)

    @staticmethod
    def resolve_clients(self, info):
        return Person.objects.filter(is_customer=True).order_by('id')

    @staticmethod
    def resolve_suppliers(self, info):
        return Person.objects.filter(is_supplier=True).order_by('id')


class OperationsMutation(graphene.ObjectType):
    person_mutation = PersonMutation.Field()
