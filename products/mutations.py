import os

import graphene

from products.models import base64_to_image_file, Product
from products.types import ProductType
from users.types import ProductInput


class ProductMutation(graphene.Mutation):
    class Arguments:
        input = ProductInput(required=True)

    success = graphene.Boolean(required=True)
    message = graphene.String(required=True)
    product = graphene.Field(ProductType)
    errors = graphene.JSONString()  # Para detalles de validación

    def mutate(self, info, input):
        errors = {}
        try:
            # === 1. Validación básica ===
            if not input.description or len(input.description.strip()) < 3:
                errors["description"] = "La descripción debe tener al menos 3 caracteres"

            if input.price_without_igv < 0 or input.price_with_igv < 0:
                errors["prices"] = "Los precios no pueden ser negativos"

            if errors:
                raise ValueError("Error de validación")

            # === 2. Obtener o crear producto ===
            if input.id:
                try:
                    product = Product.objects.get(pk=input.id)
                except Product.DoesNotExist:
                    raise ValueError("El producto no existe")
            else:
                product = Product()

            # === 3. Actualizar campos básicos ===
            product.description = input.description.strip()
            product.price_without_igv = input.price_without_igv
            product.price_with_igv = input.price_with_igv
            product.stock = input.stock or 0.0
            product.is_active = input.is_active if input.is_active is not None else True

            # === 4. Manejo de imagen (con verificación de cambios) ===
            if input.photo_base64 and input.photo_base64 != "undefined":
                try:
                    new_photo, is_new = base64_to_image_file(
                        input.photo_base64,
                        existing_file=product.photo if product.pk and product.photo else None,
                        allowed_types=("jpg", "png", "webp")  # Formatos permitidos
                    )
                    if is_new:
                        if product.photo:  # Eliminar foto anterior si existe
                            product.photo.delete(save=False)
                        product.photo.save(new_photo.name, new_photo, save=False)
                except Exception as e:
                    errors["photo"] = str(e)
                    raise

            # === 5. Guardar ===
            product.full_clean()  # Validación de modelo Django (opcional)
            product.save()

            return ProductMutation(
                success=True,
                message="Producto guardado exitosamente",
                product=product,
                errors=None
            )

        except Exception as e:
            # Log del error (opcional para debugging)
            import logging
            logging.error(f"Error en ProductMutation: {str(e)}", exc_info=True)

            return ProductMutation(
                success=False,
                message=str(e),
                product=None,
                errors=errors if errors else {"general": str(e)}
            )