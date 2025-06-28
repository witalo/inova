import os
from decimal import Decimal

import graphene
from django.core.exceptions import ValidationError
from django.db import transaction

from products.models import base64_to_image_file, Product, TypeAffectation, Unit
from products.types import ProductType, ProductInput, SaveProductResponse
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
            code_stripped = input.code.strip().upper() if input.code else ""
            description_stripped = input.description.strip().upper() if input.description else ""

            if not code_stripped:
                errors["code"] = "El código es obligatorio"
            elif len(code_stripped) < 3:
                errors["code"] = "El código debe tener al menos 3 caracteres"
            elif len(code_stripped) > 50:
                errors["code"] = "El código no puede exceder 50 caracteres"

            if not description_stripped:
                errors["description"] = "La descripción es obligatoria"
            elif len(description_stripped) < 3:
                errors["description"] = "La descripción debe tener al menos 3 caracteres"
            elif len(description_stripped) > 500:
                errors["description"] = "La descripción no puede exceder 500 caracteres"

            # Validar valores numéricos
            if input.unit_value < 0:
                errors["unit_value"] = "El valor unitario no puede ser negativo"

            if input.unit_price < 0:
                errors["unit_price"] = "El precio unitario no puede ser negativo"
            elif input.unit_price <= input.unit_value:
                errors["unit_price"] = "El precio de venta debe ser mayor que el valor unitario"

            if input.purchase_price is not None and input.purchase_price < 0:
                errors["purchase_price"] = "El precio de compra no puede ser negativo"

            if input.stock is not None and input.stock < 0:
                errors["stock"] = "El stock no puede ser negativo"

            # === 2. Validar relaciones ===
            if not errors:
                # Validar TypeAffectation
                try:
                    type_affectation = TypeAffectation.objects.get(code=input.type_affectation_id)
                except TypeAffectation.DoesNotExist:
                    errors[
                        "type_affectation_id"] = f"El tipo de afectación con código {input.type_affectation_id} no existe"

                # Validar Unit
                try:
                    unit = Unit.objects.get(id=input.unit_id)
                except Unit.DoesNotExist:
                    errors["unit_id"] = "La unidad de medida no existe"

                # Validar Company
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
                    product = Product.objects.select_for_update().get(
                        pk=product_id,
                        company_id=input.company_id  # Verificar que pertenezca a la empresa
                    )
                    is_update = True
                except Product.DoesNotExist:
                    errors["id"] = "El producto no existe o no pertenece a esta empresa"
                    return ProductMutation(
                        success=False,
                        message="Producto no encontrado",
                        product=None,
                        errors=errors
                    )
            else:
                product = Product()

            # === 4. Validar código único por empresa ===
            duplicate_query = Product.objects.filter(
                code__iexact=code_stripped,
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
            product.unit_value = Decimal(str(round(input.unit_value, 4)))
            product.unit_price = Decimal(str(round(input.unit_price, 4)))
            product.type_affectation = type_affectation
            product.unit = unit
            product.company = company

            # Campos opcionales
            if input.code_snt is not None:
                product.code_snt = input.code_snt.strip().upper() if input.code_snt else None

            if input.purchase_price is not None:
                product.purchase_price = Decimal(str(round(input.purchase_price, 4)))

            if input.stock is not None:
                product.stock = Decimal(str(round(input.stock, 4)))

            if input.is_active is not None:
                product.is_active = input.is_active

            # === 6. Manejo de imagen ===
            image_updated = False

            if getattr(input, 'remove_photo', False) and product.photo:
                # Eliminar foto actual
                product.photo.delete(save=False)
                image_updated = True

            elif hasattr(input, 'photo_base64') and input.photo_base64:
                # Limpiar el string base64
                photo_base64_clean = input.photo_base64.strip()

                if photo_base64_clean and photo_base64_clean != "undefined" and photo_base64_clean != "null":
                    try:
                        # Convertir base64 a archivo
                        image_file, is_new = base64_to_image_file(
                            photo_base64_clean,
                            existing_file=product.photo,
                            filename_prefix=f"product_{code_stripped}"
                        )

                        # Si hay nueva imagen o cambió
                        if image_file and is_new:
                            # Eliminar foto anterior si existe
                            if product.photo:
                                product.photo.delete(save=False)

                            # Guardar nueva imagen
                            product.photo.save(image_file.name, image_file, save=False)
                            image_updated = True

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

                # Log para debugging
                if image_updated:
                    print(f"Imagen {'actualizada' if is_update else 'agregada'} para producto {product.code}")

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
                errors={"general": "Ocurrió un error inesperado. Por favor, intente nuevamente."}
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


class SaveProductMutation(graphene.Mutation):
    class Arguments:
        input = ProductInput(required=True)

    Output = SaveProductResponse

    @staticmethod
    def mutate(root, info, input):
        try:
            # Validaciones
            errors = {}

            # Validar código
            if not input.code or len(input.code.strip()) < 3:
                errors['code'] = 'El código debe tener al menos 3 caracteres'
            elif len(input.code) > 50:
                errors['code'] = 'El código no puede exceder 50 caracteres'

            # Validar descripción
            if not input.description or len(input.description.strip()) < 3:
                errors['description'] = 'La descripción debe tener al menos 3 caracteres'
            elif len(input.description) > 500:
                errors['description'] = 'La descripción no puede exceder 500 caracteres'

            # Validar precios
            if input.unit_value < 0:
                errors['unit_value'] = 'El valor unitario no puede ser negativo'
            if input.unit_price < 0:
                errors['unit_price'] = 'El precio de venta no puede ser negativo'
            if input.purchase_price is not None and input.purchase_price < 0:
                errors['purchase_price'] = 'El precio de compra no puede ser negativo'
            if input.stock is not None and input.stock < 0:
                errors['stock'] = 'El stock no puede ser negativo'

            # Verificar si existe otro producto con el mismo código en la empresa
            existing_query = Product.objects.filter(
                code__iexact=input.code.strip(),
                company_id=input.company_id
            )

            if input.id:  # Si es actualización, excluir el producto actual
                existing_query = existing_query.exclude(id=input.id)

            if existing_query.exists():
                errors['code'] = f'Ya existe un producto con el código {input.code}'

            if errors:
                return SaveProductResponse(
                    success=False,
                    message='Error en la validación de datos',
                    errors=errors
                )

            # Crear o actualizar producto
            if input.id:
                # Actualizar producto existente
                product = Product.objects.get(id=input.id, company_id=input.company_id)
                product.code = input.code.strip().upper()
                product.description = input.description.strip().upper()
                product.unit_value = input.unit_value
                product.unit_price = input.unit_price

                if input.code_snt is not None:
                    product.code_snt = input.code_snt.strip().upper() if input.code_snt else None

                if input.purchase_price is not None:
                    product.purchase_price = input.purchase_price

                if input.stock is not None:
                    product.stock = input.stock

                if input.is_active is not None:
                    product.is_active = input.is_active

                message = 'Producto actualizado exitosamente'

            else:
                # Crear nuevo producto
                product = Product(
                    code=input.code.strip().upper(),
                    code_snt=input.code_snt.strip().upper() if input.code_snt else None,
                    description=input.description.strip().upper(),
                    unit_value=input.unit_value,
                    unit_price=input.unit_price,
                    purchase_price=input.purchase_price or 0,
                    stock=input.stock or 0,
                    company_id=input.company_id,
                    is_active=True
                )
                message = 'Producto creado exitosamente'

            # Asignar relaciones
            product.type_affectation_id = input.type_affectation_id
            product.unit_id = input.unit_id

            # Manejar imagen
            if input.remove_photo and product.photo:
                product.photo.delete()
                product.photo = None
            elif input.photo_base64:
                try:
                    content_file, is_new = base64_to_image_file(
                        input.photo_base64,
                        product.photo
                    )
                    if is_new and content_file:
                        if product.photo:
                            product.photo.delete()
                        product.photo = content_file
                except ValueError as e:
                    errors['photo'] = str(e)
                    return SaveProductResponse(
                        success=False,
                        message='Error al procesar la imagen',
                        errors=errors
                    )

            product.save()

            return SaveProductResponse(
                success=True,
                message=message,
                product=product
            )

        except Product.DoesNotExist:
            return SaveProductResponse(
                success=False,
                message='Producto no encontrado',
                errors={'general': 'El producto no existe o no tienes permisos para editarlo'}
            )
        except Exception as e:
            return SaveProductResponse(
                success=False,
                message=f'Error al guardar el producto: {str(e)}',
                errors={'general': str(e)}
            )