from datetime import datetime

import graphene
from django.core.exceptions import ValidationError

from products.models import Product
from products.mutations import ProductMutation
from products.types import ProductType


class ProductsQuery(graphene.ObjectType):
    products = graphene.List(ProductType)

    @staticmethod
    def resolve_products(self, info):
        return Product.objects.filter(is_active=True).order_by('id')


class ProductsMutation(graphene.ObjectType):
    product_mutation = ProductMutation.Field()

