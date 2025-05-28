import graphene
from graphene_django import DjangoObjectType

from users.models import User, Company


class CompanyType(DjangoObjectType):
    id = graphene.Int()

    class Meta:
        model = Company
        fields = (
            'id', 'ruc', 'denomination', 'address', 'phone',
            'email', 'igv_percentage', 'pdf_size', 'pdf_color',
            'created_at', 'updated_at'
        )
        # Excluir campos sensibles como password


class UserType(DjangoObjectType):
    id = graphene.Int()
    full_name = graphene.String()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'dni', 'phone', 'is_active', 'date_joined', 'company'
        )
        # Excluir password y otros campos sensibles

    def resolve_full_name(self, info):
        return f"{self.first_name} {self.last_name}"


class AuthPayload(graphene.ObjectType):
    """Payload para respuestas de autenticación"""
    success = graphene.Boolean()
    message = graphene.String()
    errors = graphene.List(graphene.String)
    token = graphene.String()
    refresh_token = graphene.String()
    user = graphene.Field(UserType)
    company = graphene.Field(CompanyType)


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
