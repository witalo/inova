import graphene
from django.db.models import Prefetch
from graphene_django import DjangoObjectType

from products.models import Product, Unit


class ProductType(DjangoObjectType):
    id = graphene.Int()

    class Meta:
        model = Product
        fields = '__all__'


class UnitType(DjangoObjectType):
    id = graphene.Int()

    class Meta:
        model = Unit
        fields = '__all__'
