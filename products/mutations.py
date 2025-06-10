import os
from decimal import Decimal

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
            # === 1. Validaciones básicas (optimizadas) ===
            code_stripped = input.code.strip() if input.code else ""
            description_stripped = input.description.strip() if input.description else ""

            if not code_stripped:
                errors["code"] = "El código es obligatorio"

            if len(description_stripped) < 3:
                errors["description"] = "La descripción debe tener al menos 3 caracteres"

            # Validar valores numéricos
            if input.unit_value < 0:
                errors["unit_value"] = "El valor unitario no puede ser negativo"

            if input.unit_price < 0:
                errors["unit_price"] = "El precio unitario no puede ser negativo"

            if input.purchase_price is not None and input.purchase_price < 0:
                errors["purchase_price"] = "El precio de compra no puede ser negativo"

            if input.stock is not None and input.stock < 0:
                errors["stock"] = "El stock no puede ser negativo"

            # === 2. Validar relaciones (con una sola consulta cuando sea posible) ===
            type_affectation = None
            unit = None
            company = None

            # CORRECCIÓN PRINCIPAL: TypeAffectation usa 'code' como PK, no 'id'
            if not errors:
                try:
                    type_affectation = TypeAffectation.objects.get(code=input.type_affectation_id)
                except TypeAffectation.DoesNotExist:
                    errors[
                        "type_affectation_id"] = f"El tipo de afectación con código {input.type_affectation_id} no existe"

                try:
                    unit = Unit.objects.get(id=input.unit_id)
                except Unit.DoesNotExist:
                    errors["unit_id"] = "La unidad de medida no existe"

                try:
                    company = Company.objects.get(id=input.company_id)
                except Company.DoesNotExist:
                    errors["company_id"] = "La empresa no existe"

            if errors:
                return ProductMutation(
                    success=False,
                    message="Error de validación",
                    product=None,
                    errors=errors
                )

            # === 3. Obtener o crear producto ===
            product_id = getattr(input, 'id', None)
            is_update = False

            if product_id and str(product_id).strip():
                try:
                    product = Product.objects.select_for_update().get(pk=product_id)
                    is_update = True
                except Product.DoesNotExist:
                    errors["id"] = "El producto no existe"
                    return ProductMutation(
                        success=False,
                        message="Producto no encontrado",
                        product=None,
                        errors=errors
                    )
            else:
                product = Product()

            # === 4. Validar código único por empresa (optimizado) ===
            duplicate_query = Product.objects.filter(
                code=code_stripped,
                company_id=input.company_id
            )

            if is_update:
                duplicate_query = duplicate_query.exclude(pk=product.pk)

            if duplicate_query.exists():
                errors["code"] = f"Ya existe un producto con el código '{code_stripped}' en esta empresa"
                return ProductMutation(
                    success=False,
                    message="Código duplicado",
                    product=None,
                    errors=errors
                )

            # === 5. Actualizar campos del producto ===
            product.code = code_stripped
            product.description = description_stripped
            product.unit_value = Decimal(str(input.unit_value))
            product.unit_price = Decimal(str(input.unit_price))
            product.type_affectation = type_affectation
            product.unit = unit
            product.company = company

            # Campos opcionales
            if input.code_snt is not None:
                product.code_snt = input.code_snt.strip() if input.code_snt else None

            if input.purchase_price is not None:
                product.purchase_price = Decimal(str(input.purchase_price))

            if input.stock is not None:
                product.stock = Decimal(str(input.stock))

            if input.is_active is not None:
                product.is_active = input.is_active

            # === 6. Manejo optimizado de imagen ===
            if input.remove_photo and product.photo:
                # Eliminar foto actual
                product.photo.delete(save=False)

            elif input.photo_base64 and input.photo_base64.strip():
                try:
                    # Eliminar foto anterior si existe
                    if product.photo:
                        product.photo.delete(save=False)

                    # Convertir base64 a archivo
                    image_file, image_format = base64_to_image_file(
                        input.photo_base64,
                        filename_prefix=f"product_{code_stripped}"
                    )

                    # Guardar nueva imagen
                    product.photo.save(image_file.name, image_file, save=False)

                except Exception as e:
                    errors["photo_base64"] = f"Error al procesar imagen: {str(e)}"
                    return ProductMutation(
                        success=False,
                        message="Error al procesar imagen",
                        product=None,
                        errors=errors
                    )

            # === 7. Guardar producto ===
            try:
                product.full_clean()
                product.save()
            except ValidationError as e:
                # Convertir errores de validación del modelo
                for field, messages in e.message_dict.items():
                    errors[field] = ', '.join(messages)

                return ProductMutation(
                    success=False,
                    message="Error de validación",
                    product=None,
                    errors=errors
                )

            return ProductMutation(
                success=True,
                message=f"Producto {'actualizado' if is_update else 'creado'} exitosamente",
                product=product,
                errors=None
            )

        except Exception as e:
            # Log del error para debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en ProductMutation: {str(e)}", exc_info=True)

            return ProductMutation(
                success=False,
                message="Error interno del servidor",
                product=None,
                errors={"general": str(e)}
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