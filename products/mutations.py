import os

import graphene
from django.core.exceptions import ValidationError
from django.db import transaction

from products.models import base64_to_image_file, Product, TypeAffectation, Unit
from products.types import ProductType, ProductInput
from users.models import Company


class ProductMutation(graphene.Mutation):
    """Mutación unificada para crear y actualizar productos"""

    class Arguments:
        input = ProductInput(required=True)

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    product = graphene.Field(ProductType)
    errors = graphene.JSONString()

    @transaction.atomic
    def mutate(self, info, input):
        errors = {}

        try:
            # === 1. Validaciones básicas ===
            # Validar campos obligatorios
            if not input.code or len(input.code.strip()) == 0:
                errors["code"] = "El código es obligatorio"

            if not input.description or len(input.description.strip()) < 3:
                errors["description"] = "La descripción debe tener al menos 3 caracteres"

            if input.unit_value < 0:
                errors["unit_value"] = "El valor unitario no puede ser negativo"

            if input.unit_price < 0:
                errors["unit_price"] = "El precio unitario no puede ser negativo"

            if input.purchase_price is not None and input.purchase_price < 0:
                errors["purchase_price"] = "El precio de compra no puede ser negativo"

            if input.stock is not None and input.stock < 0:
                errors["stock"] = "El stock no puede ser negativo"

            # === 2. Validar relaciones ===
            try:
                type_affectation = TypeAffectation.objects.get(id=input.type_affectation_id)
            except TypeAffectation.DoesNotExist:
                errors["type_affectation_id"] = "El tipo de afectación no existe"

            try:
                unit = Unit.objects.get(id=input.unit_id)
            except Unit.DoesNotExist:
                errors["unit_id"] = "La unidad de medida no existe"

            try:
                company = Company.objects.get(id=input.company_id)
            except Company.DoesNotExist:
                errors["company_id"] = "La empresa no existe"

            if errors:
                raise ValueError("Errores de validación")

            # === 3. Obtener o crear producto ===
            if input.id:
                # Actualización
                try:
                    product = Product.objects.get(pk=input.id)
                    is_update = True
                except Product.DoesNotExist:
                    errors["id"] = "El producto no existe"
                    raise ValueError("Producto no encontrado")
            else:
                # Creación
                product = Product()
                is_update = False

            # === 4. Validar código único por empresa ===
            code_exists = Product.objects.filter(
                code=input.code.strip(),
                company_id=input.company_id
            ).exclude(pk=product.pk if is_update else None).exists()

            if code_exists:
                errors["code"] = f"Ya existe un producto con el código '{input.code}' en esta empresa"
                raise ValueError("Código duplicado")

            # === 5. Actualizar campos ===
            product.code = input.code.strip()
            product.description = input.description.strip()
            product.unit_value = input.unit_value
            product.unit_price = input.unit_price
            product.type_affectation = type_affectation
            product.unit = unit
            product.company = company

            # Campos opcionales
            if input.code_snt is not None:
                product.code_snt = input.code_snt.strip() if input.code_snt else None

            if input.purchase_price is not None:
                product.purchase_price = input.purchase_price

            if input.stock is not None:
                product.stock = input.stock

            if input.is_active is not None:
                product.is_active = input.is_active

            # === 6. Manejo de imagen ===
            if input.remove_photo and product.photo:
                # Eliminar foto actual
                old_photo_path = product.photo.path if product.photo else None
                product.photo = None
                # Eliminar archivo físico
                if old_photo_path and os.path.isfile(old_photo_path):
                    try:
                        os.remove(old_photo_path)
                    except Exception:
                        pass  # Ignorar error si no se puede eliminar

            elif input.photo_base64 and input.photo_base64.strip():
                try:
                    # Eliminar foto anterior si existe
                    if product.photo:
                        old_photo_path = product.photo.path
                        product.photo.delete(save=False)
                        if old_photo_path and os.path.isfile(old_photo_path):
                            try:
                                os.remove(old_photo_path)
                            except Exception:
                                pass  # Ignorar error si no se puede eliminar

                    # Convertir base64 a archivo
                    image_file, image_format = base64_to_image_file(
                        input.photo_base64,
                        filename_prefix=f"product_{input.code}"
                    )

                    # Guardar nueva imagen
                    product.photo.save(image_file.name, image_file, save=False)

                except Exception as e:
                    errors["photo_base64"] = str(e)
                    raise ValueError(f"Error al procesar imagen: {str(e)}")

            # === 7. Guardar producto ===
            product.full_clean()  # Validación adicional del modelo
            product.save()

            return ProductMutation(
                success=True,
                message=f"Producto {'actualizado' if is_update else 'creado'} exitosamente",
                product=product,
                errors=None
            )

        except ValidationError as e:
            # Errores de validación del modelo
            for field, messages in e.message_dict.items():
                errors[field] = ', '.join(messages)

            return ProductMutation(
                success=False,
                message="Error de validación",
                product=None,
                errors=errors
            )

        except Exception as e:
            return ProductMutation(
                success=False,
                message=str(e) if not errors else "Errores de validación",
                product=None,
                errors=errors if errors else {"general": str(e)}
            )


class DeleteProductMutation(graphene.Mutation):
    """Mutación para eliminar un producto"""

    class Arguments:
        id = graphene.ID(required=True)

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    errors = graphene.JSONString()

    @transaction.atomic
    def mutate(self, info, id):
        try:
            product = Product.objects.get(pk=id)

            # Eliminar foto si existe
            if product.photo:
                photo_path = product.photo.path
                product.photo.delete(save=False)
                if photo_path and os.path.isfile(photo_path):
                    try:
                        os.remove(photo_path)
                    except Exception:
                        pass  # Ignorar error si no se puede eliminar

            # Eliminar producto
            product.delete()

            return DeleteProductMutation(
                success=True,
                message="Producto eliminado exitosamente",
                errors=None
            )

        except Product.DoesNotExist:
            return DeleteProductMutation(
                success=False,
                message="El producto no existe",
                errors={"id": "Producto no encontrado"}
            )
        except Exception as e:
            return DeleteProductMutation(
                success=False,
                message=f"Error al eliminar producto: {str(e)}",
                errors={"general": str(e)}
            )