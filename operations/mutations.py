import os
import re

import graphene

from operations.models import Person
from operations.types import PersonInput, PersonType


class PersonMutation(graphene.Mutation):
    class Arguments:
        input = PersonInput(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    person = graphene.Field(PersonType)
    errors = graphene.JSONString()

    @staticmethod
    def mutate(root, info, input):
        errors = {}
        person = None

        try:
            # === Validaciones ===
            # Validar tipo de documento
            if input.person_type not in dict(Person.PERSON_TYPE_CHOICES).keys():
                errors["person_type"] = f"Tipo inválido. Opciones: {dict(Person.PERSON_TYPE_CHOICES)}"

            # Validar formato del número según tipo
            if input.person_type == '1' and not input.person_number.isdigit() or len(input.person_number) != 8:
                errors["person_number"] = "DNI requiere 8 dígitos numéricos"
            elif input.person_type == '6' and not input.person_number.isdigit() or len(input.person_number) != 11:
                errors["person_number"] = "RUC requiere 11 dígitos numéricos"

            # Validar email si existe
            if input.email and not re.match(r"[^@]+@[^@]+\.[^@]+", input.email):
                errors["email"] = "Formato de email inválido"

            if errors:
                raise ValueError("Errores de validación")

            # === Obtener o crear persona ===
            if input.id:
                try:
                    person = Person.objects.get(pk=input.id)
                except Person.DoesNotExist:
                    raise ValueError("Persona no encontrada")
            else:
                if Person.objects.filter(person_number=input.person_number).exists():
                    raise ValueError("Ya existe una persona con este documento")
                person = Person()

            # === Actualizar campos ===
            person.person_type = input.person_type
            person.person_number = input.person_number
            person.full_name = input.full_name.strip()
            person.is_customer = input.is_customer if input.is_customer is not None else False
            person.is_supplier = input.is_supplier if input.is_supplier is not None else False
            person.address = input.address.strip() if input.address else None
            person.phone = input.phone.strip() if input.phone else None
            person.email = input.email.lower().strip() if input.email else None

            # === Guardar ===
            person.full_clean()  # Validación de modelo Django
            person.save()

            return PersonMutation(
                success=True,
                message="Persona guardada exitosamente",
                person=person,
                errors=None
            )

        except Exception as e:
            return PersonMutation(
                success=False,
                message=str(e),
                person=person,
                errors=errors if errors else {"general": str(e)}
            )