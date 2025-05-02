import graphene
from graphene_django import DjangoObjectType

from users.models import User


class UserType(DjangoObjectType):
    id = graphene.Int()

    class Meta:
        model = User
        fields = '__all__'


class ProductInput(graphene.InputObjectType):
    id = graphene.ID(description="Solo necesario para actualización")
    code = graphene.String(description="Código interno del producto")
    code_snt = graphene.String(description="Código SUNAT (opcional)")
    description = graphene.String(required=True, description="Nombre/descripción del producto")
    price_without_igv = graphene.Float(
        required=True,
        description="Precio sin IGV (debe ser >= 0)"
    )
    price_with_igv = graphene.Float(
        required=True,
        description="Precio con IGV (debe ser >= 0)"
    )
    stock = graphene.Float(
        required=False,
        description="Stock disponible (opcional, default=0)"
    )
    type_affectation_id = graphene.ID(
        required=False,
        description="ID del tipo de afectación (IGV, etc.)"
    )
    unit_id = graphene.ID(
        required=False,
        description="ID de la unidad de medida (ej. 'UNIDAD', 'KG')"
    )
    photo_base64 = graphene.String(
        required=False,
        description="Imagen en base64 (formatos: jpg, png, webp)"
    )
    is_active = graphene.Boolean(
        required=False,
        default=True,
        description="¿Producto activo? (default=True)"
    )
