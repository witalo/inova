import base64
import os

import graphene
from graphene_django import DjangoObjectType

from users.models import User, Company


class CompanyType(DjangoObjectType):
    id = graphene.Int()
    logo_base64 = graphene.String()

    class Meta:
        model = Company
        fields = (
            'id', 'ruc', 'denomination', 'address', 'phone',
            'email', 'igv_percentage', 'pdf_size', 'pdf_color',
            'is_active'
        )

        def resolve_logo_base64(self, info):
            """
            Convierte el logo de la empresa a base64
            """
            try:
                # Si la empresa tiene logo
                if self.logo and hasattr(self.logo, 'path'):
                    # Verificar que el archivo existe
                    if os.path.exists(self.logo.path):
                        with open(self.logo.path, "rb") as img_file:
                            # Leer y convertir a base64
                            logo_data = base64.b64encode(img_file.read()).decode('utf-8')

                            # Detectar el tipo de imagen
                            file_extension = os.path.splitext(self.logo.path)[1].lower()

                            if file_extension in ['.png']:
                                mime_type = "image/png"
                            elif file_extension in ['.jpg', '.jpeg']:
                                mime_type = "image/jpeg"
                            elif file_extension in ['.gif']:
                                mime_type = "image/gif"
                            elif file_extension in ['.webp']:
                                mime_type = "image/webp"
                            else:
                                # Por defecto asumir PNG
                                mime_type = "image/png"

                            # Retornar con el prefijo data URL
                            return f"data:{mime_type};base64,{logo_data}"

                # Si no hay logo, retornar None
                return None

            except Exception as e:
                print(f"Error al convertir logo a base64: {e}")
                return None


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


