import io

from PIL.Image import Image
from django.db import models

# Create your models here.
import hashlib
from django.core.files.base import ContentFile
import base64
import imghdr
import uuid
import base64
import imghdr


def base64_to_image_file(base64_string, existing_file=None, allowed_types=("jpeg", "jpg", "png", "webp"),
                         filename_prefix=None):
    """
    Convierte un base64 en ContentFile, con validación de formato y comparación con archivo existente.

    Args:
        base64_string (str): Imagen en base64 (con o sin encabezado).
        existing_file (FileField): Archivo existente (opcional).
        allowed_types (tuple): Formatos permitidos (extensiones).
        filename_prefix (str): Prefijo para el nombre del archivo (opcional).

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

        # Decodificar
        decoded_file = base64.b64decode(data)

        # Validar que sea una imagen válida usando PIL
        try:
            img = Image.open(io.BytesIO(decoded_file))
            img.verify()  # Verificar que sea una imagen válida

            # Reabrir porque verify() cierra el archivo
            img = Image.open(io.BytesIO(decoded_file))

            # Obtener formato real
            file_type = img.format.lower()
            if file_type == "jpeg":
                file_type = "jpg"

        except Exception:
            # Si PIL falla, intentar con imghdr
            file_type = imghdr.what(None, h=decoded_file)
            if not file_type:
                raise ValueError("No se pudo detectar el tipo de imagen o el archivo no es una imagen válida")

        file_type = file_type.lower()

        # Validar formato permitido
        if file_type not in allowed_types:
            raise ValueError(f"Formato '{file_type}' no permitido. Use: {', '.join(allowed_types)}")

        # Validar coincidencia entre format_part (header) y file_type (real)
        if format_part and format_part != file_type:
            # Solo advertir, no fallar
            print(f"Advertencia: El header indica '{format_part}' pero el archivo es '{file_type}'")

        # Calcular hash del nuevo archivo
        new_file_hash = hashlib.md5(decoded_file).hexdigest()

        # Comparar con archivo existente (si existe)
        if existing_file and existing_file.name:
            try:
                existing_file.open('rb')
                existing_data = existing_file.read()
                existing_hash = hashlib.md5(existing_data).hexdigest()
                existing_file.close()

                if new_file_hash == existing_hash:
                    return None, False  # No hay cambios, misma imagen
            except Exception as e:
                print(f"Error al comparar con imagen existente: {e}")
                # Continuar como si fuera nueva

        # Crear nuevo archivo
        if filename_prefix:
            filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.{file_type}"
        else:
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
    code = models.CharField(max_length=50, null=True, blank=True)
    code_snt = models.CharField(max_length=20, null=True, blank=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    unit_value = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    unit_price = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    purchase_price = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    stock = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    type_affectation = models.ForeignKey('TypeAffectation', on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True, blank=True)
    photo = models.ImageField('Foto', upload_to='products/', blank=True, null=True)
    company = models.ForeignKey('users.Company', on_delete=models.SET_NULL, null=True, blank=True)
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
