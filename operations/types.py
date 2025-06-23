import graphene
from django.db.models import Prefetch
from graphene_django import DjangoObjectType

from operations.models import Person, Document, Serial, Operation, OperationDetail
from products.models import Product, Unit
from products.types import TopProductType


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


class DocumentType(DjangoObjectType):
    class Meta:
        model = Document
        fields = '__all__'


class SerialType(DjangoObjectType):
    class Meta:
        model = Serial
        fields = '__all__'


class PersonType(DjangoObjectType):
    class Meta:
        model = Person
        fields = '__all__'


class OperationType(DjangoObjectType):
    details = graphene.List(lambda: OperationDetailType)

    class Meta:
        model = Operation
        fields = '__all__'

    def resolve_details(self, info):
        return self.operationdetail_set.all()


class OperationDetailType(DjangoObjectType):
    class Meta:
        model = OperationDetail
        fields = '__all__'


class OperationDetailType(DjangoObjectType):
    class Meta:
        model = OperationDetail
        fields = '__all__'


# Types para resumen
class SalesSummaryType(graphene.ObjectType):
    total_sales = graphene.Int()
    total_amount = graphene.Float()
    total_igv = graphene.Float()
    total_discount = graphene.Float()
    average_ticket = graphene.Float()
    top_products = graphene.List(TopProductType)


# Input Types
class OperationDetailInput(graphene.InputObjectType):
    product_id = graphene.ID(required=True)
    quantity = graphene.Float(required=True)
    unit_value = graphene.Float(required=True)
    unit_price = graphene.Float(required=True)
    discount_percentage = graphene.Float(default_value=0)
    type_affectation_id = graphene.ID(required=True)
