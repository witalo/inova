import graphene
from django.db.models import Prefetch
from graphene_django import DjangoObjectType

from operations.models import Person
from products.models import Product, Unit


class PersonType(DjangoObjectType):
    class Meta:
        model = Person
        fields = "__all__"
        interfaces = (graphene.relay.Node,)

    person_type_display = graphene.String(description="Nombre del tipo de documento")

    def resolve_person_type_display(self, info):
        return self.get_person_type_display()


class PersonInput(graphene.InputObjectType):
    id = graphene.ID(description="ID solo para actualización")
    person_type = graphene.String(required=True, description="Tipo de documento: 1 (DNI) o 6 (RUC)")
    person_number = graphene.String(required=True, description="Número de documento (8 dígitos para DNI, 11 para RUC)")
    full_name = graphene.String(required=True, description="Nombre completo")
    is_customer = graphene.Boolean(description="¿Es cliente? (default=False)")
    is_supplier = graphene.Boolean(description="¿Es proveedor? (default=False)")
    address = graphene.String(description="Dirección completa")
    phone = graphene.String(description="Teléfono (opcional)")
    email = graphene.String(description="Email (opcional, validado)")
