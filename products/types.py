import imghdr

import graphene
import base64
import uuid
import os
import imghdr
from PIL import Image
from io import BytesIO

from django.core.files.base import ContentFile
from graphene_django import DjangoObjectType

from products.models import Product, Unit, TypeAffectation


class ProductType(DjangoObjectType):
    photo_base64 = graphene.String(description="Imagen del producto en base64")

    class Meta:
        model = Product
        fields = '__all__'

    def resolve_photo_base64(self, info):
        """Convierte la imagen almacenada a base64 para enviar al frontend"""
        if self.photo and self.photo.name:
            try:
                with self.photo.open('rb') as image_file:
                    image_data = image_file.read()
                    # Detectar el tipo de imagen
                    image_type = imghdr.what(None, h=image_data)
                    if not image_type:
                        image_type = 'jpeg'
                    # Convertir a base64
                    base64_string = base64.b64encode(image_data).decode('utf-8')
                    return f"data:image/{image_type};base64,{base64_string}"
            except Exception as e:
                # Silenciosamente retornar None si hay error
                return None
        return None


class TypeAffectationType(DjangoObjectType):
    class Meta:
        model = TypeAffectation
        fields = '__all__'


class UnitType(DjangoObjectType):
    id = graphene.Int()

    class Meta:
        model = Unit
        fields = '__all__'


class ProductInput(graphene.InputObjectType):
    id = graphene.ID(description="Solo necesario para actualización")
    code = graphene.String(required=True, description="Código interno del producto")
    code_snt = graphene.String(description="Código SUNAT (opcional)")
    description = graphene.String(required=True, description="Nombre/descripción del producto")
    unit_value = graphene.Float(
        required=True,
        description="Valor unitario (debe ser >= 0)"
    )
    unit_price = graphene.Float(
        required=True,
        description="Precio unitario (debe ser >= 0)"
    )
    purchase_price = graphene.Float(
        description="Precio de compra (opcional)"
    )
    stock = graphene.Float(
        description="Stock disponible (opcional, default=0)"
    )
    type_affectation_id = graphene.ID(
        required=True,
        description="ID del tipo de afectación (IGV, etc.)"
    )
    unit_id = graphene.ID(
        required=True,
        description="ID de la unidad de medida (ej. 'UNIDAD', 'KG')"
    )
    company_id = graphene.ID(
        required=True,
        description="ID de la empresa"
    )
    photo_base64 = graphene.String(
        description="Imagen en base64 (formatos: jpg, png, webp)"
    )
    remove_photo = graphene.Boolean(
        description="Si es True, elimina la foto actual sin agregar una nueva"
    )
    is_active = graphene.Boolean(
        description="¿Producto activo? (default=True)"
    )


def base64_to_image_file(base64_string, filename_prefix="product"):
    """
    Convierte una imagen base64 a un archivo ContentFile de Django

    Args:
        base64_string: String en formato base64 o data URI
        filename_prefix: Prefijo para el nombre del archivo

    Returns:
        tuple: (ContentFile, formato_imagen)
    """
    try:
        # Remover el prefijo data:image/xxx;base64, si existe
        if 'base64,' in base64_string:
            format_prefix, base64_data = base64_string.split('base64,')
            # Extraer el formato de imagen del prefijo
            image_format = format_prefix.split('/')[-1].split(';')[0]
        else:
            base64_data = base64_string
            image_format = None

        # Decodificar base64
        image_data = base64.b64decode(base64_data)

        # Validar que sea una imagen válida usando PIL
        img = Image.open(BytesIO(image_data))

        # Detectar formato si no se especificó
        if not image_format:
            image_format = img.format.lower()

        # Validar formatos permitidos
        allowed_formats = ['jpeg', 'jpg', 'png', 'webp']
        if image_format not in allowed_formats:
            raise ValueError(
                f"Formato de imagen no permitido: {image_format}. Formatos permitidos: {', '.join(allowed_formats)}")

        # Optimizar imagen si es necesario (opcional)
        if img.width > 1920 or img.height > 1920:
            img.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format=image_format.upper(), quality=85)
            image_data = buffer.getvalue()

        # Generar nombre único para el archivo
        filename = f"{filename_prefix}_{uuid.uuid4().hex}.{image_format}"

        return ContentFile(image_data, name=filename), image_format

    except Exception as e:
        raise ValueError(f"Error al procesar imagen: {str(e)}")
