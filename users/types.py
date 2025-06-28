import base64
import os
import imghdr
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
    photo_base64 = graphene.String(description="Foto del usuario en base64")

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'dni', 'phone', 'is_active', 'date_joined', 'company', 'photo'
        )
        # Excluir password y otros campos sensibles

    def resolve_full_name(self, info):
        return f"{self.first_name} {self.last_name}"

    def resolve_photo_base64(self, info):
        """Convierte la imagen almacenada a base64 para enviar al frontend"""
        if self.photo and self.photo.name:
            try:
                # Abrir y leer la imagen
                self.photo.open('rb')
                image_data = self.photo.read()
                self.photo.close()

                # Detectar el tipo de imagen usando múltiples métodos
                image_type = None

                # Método 1: Por extensión del archivo
                if '.' in self.photo.name:
                    ext = self.photo.name.split('.')[-1].lower()
                    if ext in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                        image_type = 'jpeg' if ext == 'jpg' else ext

                # Método 2: Por contenido usando imghdr
                if not image_type:
                    detected_type = imghdr.what(None, h=image_data)
                    if detected_type:
                        image_type = detected_type

                # Fallback
                if not image_type:
                    image_type = 'jpeg'

                # Convertir a base64
                base64_string = base64.b64encode(image_data).decode('utf-8')
                return f"data:image/{image_type};base64,{base64_string}"

            except Exception as e:
                print(f"Error al convertir imagen a base64: {e}")
                return None
        return None


class AuthPayload(graphene.ObjectType):
    """Payload para respuestas de autenticación"""
    success = graphene.Boolean()
    message = graphene.String()
    errors = graphene.List(graphene.String)
    token = graphene.String()
    refresh_token = graphene.String()
    user = graphene.Field(UserType)
    company = graphene.Field(CompanyType)
