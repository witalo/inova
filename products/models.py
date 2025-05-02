from django.db import models

# Create your models here.
import hashlib
from django.core.files.base import ContentFile
import base64
import imghdr
import uuid


def base64_to_image_file(base64_string, existing_file=None, allowed_types=("jpeg", "jpg", "png", "webp")):
    """
    Convierte un base64 en ContentFile, con validación de formato y comparación con archivo existente.

    Args:
        base64_string (str): Imagen en base64 (con o sin encabezado).
        existing_file (FileField): Archivo existente (opcional).
        allowed_types (tuple): Formatos permitidos (extensiones).

    Returns:
        tuple: (ContentFile, is_new)
               - ContentFile: Archivo generado (None si no hay cambios)
               - is_new: True si es diferente al existente o no existía

    Raises:
        ValueError: Si la imagen no es válida o el formato no coincide.
    """
    if not base64_string or base64_string.strip() == "" or base64_string == "undefined":
        return None, False

    try:
        # Extraer metadata y datos
        if ";" in base64_string and "," in base64_string:
            header, data = base64_string.split(";base64,")
            format_part = header.split("/")[-1].lower().strip()
            if format_part == "jpeg":  # Normalizar jpeg -> jpg
                format_part = "jpg"
        else:
            data = base64_string
            format_part = None

        # Decodificar y detectar tipo real
        decoded_file = base64.b64decode(data)
        file_type = imghdr.what(None, h=decoded_file)

        if not file_type:
            raise ValueError("No se pudo detectar el tipo de imagen")

        file_type = file_type.lower()  # Asegurar minúsculas

        # Validar formato permitido
        if file_type not in allowed_types:
            raise ValueError(f"Formato '{file_type}' no permitido. Use: {', '.join(allowed_types)}")

        # Validar coincidencia entre format_part (header) y file_type (real)
        if format_part and format_part != file_type:
            raise ValueError(
                f"Conflicto de formatos: Encabezado dice '{format_part}' "
                f"pero el archivo es '{file_type}'"
            )

        # Comparar con archivo existente (si existe)
        new_file_hash = hashlib.md5(decoded_file).hexdigest()
        if existing_file and existing_file.name:
            existing_file.open('rb')
            existing_hash = hashlib.md5(existing_file.read()).hexdigest()
            existing_file.close()

            if new_file_hash == existing_hash:
                return None, False  # No hay cambios

        # Crear nuevo archivo si es necesario
        filename = f"{uuid.uuid4()}.{file_type}"
        return ContentFile(decoded_file, name=filename), True

    except Exception as e:
        raise ValueError(f"Error al procesar imagen: {str(e)}")


class TypeAffectation(models.Model):
    code = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Tipo de afectación'
        verbose_name_plural = 'Tipos de afectación'


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=20, null=True, blank=True)
    code_snt = models.CharField(max_length=20, null=True, blank=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    price_without_igv = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    price_with_igv = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    stock = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    type_affectation = models.ForeignKey('TypeAffectation', on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True, blank=True)
    photo = models.ImageField('Foto', upload_to='products/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.description)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'


class Unit(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.description)

    class Meta:
        verbose_name = 'Unidad'
        verbose_name_plural = 'Unidades'
