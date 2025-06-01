import base64
import os
import re

import graphene
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import validate_email
from graphql_jwt.shortcuts import get_token
from graphql_jwt.refresh_token.shortcuts import create_refresh_token, get_refresh_token
from django.contrib.auth.hashers import check_password
from users.models import User, Company
from users.types import UserType, CompanyType


class CompanyLoginMutation(graphene.Mutation):
    """
    Primer login: Validación de empresa con RUC, email y contraseña
    """

    class Arguments:
        ruc = graphene.String(required=True)
        email = graphene.String(required=True)
        password = graphene.String(required=True)

    # Respuesta
    success = graphene.Boolean()
    message = graphene.String()
    company = graphene.Field(CompanyType)
    logo_base64 = graphene.String()
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, ruc, email, password):
        errors = []

        try:
            # Validar formato RUC (11 dígitos para Perú)
            if not ruc or len(ruc) != 11 or not ruc.isdigit():
                errors.append("RUC debe tener 11 dígitos numéricos")

            # Validar email
            if not email or '@' not in email:
                errors.append("Email inválido")

            # Validar contraseña
            if not password or len(password) < 4:
                errors.append("Contraseña debe tener al menos 6 caracteres")

            if errors:
                print(errors)
                return CompanyLoginMutation(
                    success=False,
                    message="Datos inválidos",
                    errors=errors
                )

            # Buscar empresa
            try:
                company = Company.objects.get(ruc=ruc, email__iexact=email)
            except Company.DoesNotExist:
                return CompanyLoginMutation(
                    success=False,
                    message="Empresa no encontrada. Verifique RUC y email.",
                    errors=["Credenciales de empresa incorrectas"]
                )

            # Validar contraseña de empresa
            if not check_password(password, company.password):
                return CompanyLoginMutation(
                    success=False,
                    message="Contraseña de empresa incorrecta",
                    errors=["Credenciales incorrectas"]
                )

            # Convertir logo a base64 si existe
            logo_base64 = None
            if company.logo:
                try:
                    with open(company.logo.path, "rb") as img_file:
                        logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                        # Agregar el prefijo data URL
                        logo_base64 = f"data:image/png;base64,{logo_base64}"
                except Exception as e:
                    print(f"Error al convertir logo: {e}")

            return CompanyLoginMutation(
                success=True,
                message="Login de empresa exitoso",
                company=company,
                logo_base64=logo_base64,
                errors=[]
            )

        except Exception as e:
            return CompanyLoginMutation(
                success=False,
                message="Error interno del servidor",
                errors=[str(e)]
            )


class UserLoginMutation(graphene.Mutation):
    """
    Segundo login: Validación de usuario con username/email y contraseña
    """

    class Arguments:
        username = graphene.String(required=True)  # Puede ser email o username
        password = graphene.String(required=True)
        company_id = graphene.ID(required=True)

    # Respuesta
    success = graphene.Boolean()
    message = graphene.String()
    token = graphene.String()
    refresh_token = graphene.String()
    user = graphene.Field(UserType)
    company = graphene.Field(CompanyType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, username, password, company_id):
        errors = []

        try:
            # Validaciones básicas
            if not username or len(username) < 3:
                errors.append("Usuario/email requerido")

            if not password or len(password) < 4:
                errors.append("Contraseña debe tener al menos 6 caracteres")

            if errors:
                return UserLoginMutation(
                    success=False,
                    message="Datos inválidos",
                    errors=errors
                )

            # Verificar que la empresa existe
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                return UserLoginMutation(
                    success=False,
                    message="Empresa no válida",
                    errors=["Empresa no encontrada"]
                )

            # Buscar usuario por email o username en la empresa
            user = None
            try:
                # Intentar buscar por email primero
                if '@' in username:
                    user = User.objects.get(
                        email__iexact=username,
                        company=company,
                        is_active=True
                    )
                else:
                    # Buscar por username
                    user = User.objects.get(
                        username__iexact=username,
                        company=company,
                        is_active=True
                    )
            except User.DoesNotExist:
                return UserLoginMutation(
                    success=False,
                    message="Usuario no encontrado o inactivo",
                    errors=["Credenciales incorrectas"]
                )
            except User.MultipleObjectsReturned:
                return UserLoginMutation(
                    success=False,
                    message="Error: múltiples usuarios encontrados",
                    errors=["Contacte al administrador"]
                )

            # Autenticar usuario
            auth_user = authenticate(username=user.username, password=password)
            if not auth_user:
                return UserLoginMutation(
                    success=False,
                    message="Contraseña incorrecta",
                    errors=["Credenciales incorrectas"]
                )

            # Verificar que el usuario pertenece a la empresa
            if auth_user.company != company:
                return UserLoginMutation(
                    success=False,
                    message="Usuario no autorizado para esta empresa",
                    errors=["Acceso denegado"]
                )

            # Generar tokens JWT
            token = get_token(auth_user)
            refresh_token = create_refresh_token(auth_user)
            # refresh_token = get_refresh_token(auth_user)  # Ahora usando la función importada directamente

            return UserLoginMutation(
                success=True,
                message="Login exitoso",
                token=token,
                refresh_token=refresh_token,
                user=auth_user,
                company=company,
                errors=[]
            )

        except Exception as e:
            print("Error:", e)
            return UserLoginMutation(
                success=False,
                message="Error interno del servidor",
                errors=[str(e)]
            )


class CreateUserMutation(graphene.Mutation):
    class Arguments:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        dni = graphene.String(required=True)
        phone = graphene.String()
        password = graphene.String(required=True)
        email = graphene.String(required=True)
        company_id = graphene.ID(required=True)
        is_active = graphene.Boolean()

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, first_name, last_name, dni, password, email, company_id, phone=None, is_active=True):
        errors = []

        try:
            # Validaciones
            if User.objects.filter(email__iexact=email).exists():
                errors.append("Email ya está registrado")

            if User.objects.filter(dni=dni).exists():
                errors.append("DNI ya está registrado")

            if len(password) < 6:
                errors.append("Contraseña debe tener al menos 6 caracteres")
            company = None
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                errors.append("Empresa no válida")

            if errors:
                return CreateUserMutation(
                    success=False,
                    message="Errores en los datos",
                    errors=errors
                )

            # Crear usuario
            user = User.objects.create_user(
                username=email,  # Usar email como username
                email=email,
                password=password,
                first_name=first_name.upper(),
                last_name=last_name.upper(),
                dni=dni,
                phone=phone,
                company=company,
                is_active=is_active
            )

            return CreateUserMutation(
                success=True,
                message="Usuario creado exitosamente",
                user=user,
                errors=[]
            )

        except Exception as e:
            return CreateUserMutation(
                success=False,
                message="Error al crear usuario",
                errors=[str(e)]
            )


class UpdateUserMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        dni = graphene.String()
        phone = graphene.String()
        password = graphene.String()
        email = graphene.String()
        is_active = graphene.Boolean()

    success = graphene.Boolean()
    message = graphene.String()
    user = graphene.Field(UserType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, id, **kwargs):
        errors = []

        try:
            user = User.objects.get(pk=id)

            # Validar email único si se está cambiando
            if 'email' in kwargs and kwargs['email'] != user.email:
                if User.objects.filter(email__iexact=kwargs['email']).exists():
                    errors.append("Email ya está registrado")

            # Validar DNI único si se está cambiando
            if 'dni' in kwargs and kwargs['dni'] != user.dni:
                if User.objects.filter(dni=kwargs['dni']).exists():
                    errors.append("DNI ya está registrado")

            if errors:
                return UpdateUserMutation(
                    success=False,
                    message="Errores en los datos",
                    errors=errors
                )

            # Actualizar campos
            for field, value in kwargs.items():
                if field == 'password' and value and value != 'undefined':
                    user.set_password(value)
                elif field in ['first_name', 'last_name'] and value:
                    setattr(user, field, value.upper())
                elif value is not None:
                    setattr(user, field, value)

            user.save()

            return UpdateUserMutation(
                success=True,
                message="Usuario actualizado exitosamente",
                user=user,
                errors=[]
            )

        except User.DoesNotExist:
            return UpdateUserMutation(
                success=False,
                message="Usuario no encontrado",
                errors=["Usuario no existe"]
            )
        except Exception as e:
            return UpdateUserMutation(
                success=False,
                message="Error al actualizar usuario",
                errors=[str(e)]
            )

class CreateCompanyMutation(graphene.Mutation):
    """
    Crear nueva empresa con validaciones completas
    """

    class Arguments:
        ruc = graphene.String(required=True)
        denomination = graphene.String(required=True)
        address = graphene.String()
        phone = graphene.String()
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        logo_base64 = graphene.String()
        igv_percentage = graphene.Int()
        pdf_size = graphene.String()
        pdf_color = graphene.String()

    # Respuesta
    success = graphene.Boolean()
    message = graphene.String()
    company = graphene.Field(CompanyType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, ruc, denomination, email, password, **kwargs):
        errors = []

        try:
            # Validar RUC (11 dígitos para Perú)
            if not ruc or len(ruc) != 11 or not ruc.isdigit():
                errors.append("RUC debe tener 11 dígitos numéricos")

            # Verificar si RUC ya existe
            if Company.objects.filter(ruc=ruc).exists():
                errors.append("Ya existe una empresa con este RUC")

            # Validar denominación/razón social
            if not denomination or len(denomination.strip()) < 3:
                errors.append("La razón social debe tener al menos 3 caracteres")
            elif len(denomination) > 150:
                errors.append("La razón social no puede exceder 150 caracteres")

            # Validar email
            if not email:
                errors.append("Email es requerido")
            else:
                try:
                    validate_email(email)
                except ValidationError:
                    errors.append("Formato de email inválido")

                # Verificar si email ya existe
                if Company.objects.filter(email__iexact=email).exists():
                    errors.append("Ya existe una empresa con este email")

            # Validar contraseña
            if not password or len(password) < 6:
                errors.append("La contraseña debe tener al menos 6 caracteres")
            elif len(password) > 128:
                errors.append("La contraseña no puede exceder 128 caracteres")

            # Validar campos opcionales
            address = kwargs.get('address', '')
            if address and len(address) > 200:
                errors.append("La dirección no puede exceder 200 caracteres")

            phone = kwargs.get('phone', '')
            if phone:
                # Validar formato de teléfono (solo números, espacios, guiones y paréntesis)
                if not re.match(r'^[\d\s\-\(\)\+]+$', phone):
                    errors.append("Formato de teléfono inválido")
                elif len(phone) > 45:
                    errors.append("El teléfono no puede exceder 45 caracteres")

            # Validar IGV
            igv_percentage = kwargs.get('igv_percentage', 18)
            valid_igv_values = [18, 10, 4]
            if igv_percentage not in valid_igv_values:
                errors.append("IGV debe ser 18%, 10% o 4%")

            # Validar tamaño PDF
            pdf_size = kwargs.get('pdf_size', 'T')
            valid_pdf_sizes = ['T', 'A']
            if pdf_size not in valid_pdf_sizes:
                errors.append("Tamaño de PDF debe ser 'T' (Ticket) o 'A' (A4)")

            # Validar color PDF (formato hexadecimal)
            pdf_color = kwargs.get('pdf_color', '#000000')
            if not re.match(r'^#[0-9A-Fa-f]{6}$', pdf_color):
                errors.append("Color PDF debe estar en formato hexadecimal (#RRGGBB)")

            # Validar logo base64
            logo_base64 = kwargs.get('logo_base64')
            logo_file = None
            if logo_base64:
                try:
                    # Remover prefijo data:image si existe
                    if logo_base64.startswith('data:image'):
                        logo_base64 = logo_base64.split(',')[1]

                    # Decodificar base64
                    logo_data = base64.b64decode(logo_base64)

                    # Validar tamaño (máximo 5MB)
                    if len(logo_data) > 5 * 1024 * 1024:
                        errors.append("El logo no puede exceder 5MB")
                    else:
                        # Crear archivo temporal
                        logo_file = ContentFile(logo_data, name=f"logo_{ruc}.png")

                except Exception as e:
                    errors.append("Error al procesar el logo: formato base64 inválido")

            if errors:
                return CreateCompanyMutation(
                    success=False,
                    message="Datos inválidos",
                    errors=errors
                )

            # Crear la empresa
            company = Company(
                ruc=ruc,
                denomination=denomination.strip(),
                address=address.strip() if address else '',
                phone=phone.strip() if phone else '',
                email=email.lower().strip(),
                igv_percentage=igv_percentage,
                pdf_size=pdf_size,
                pdf_color=pdf_color
            )

            # Establecer contraseña encriptada
            company.set_password(password)

            # Asignar logo si existe
            if logo_file:
                company.logo = logo_file

            # Guardar la empresa
            company.save()

            return CreateCompanyMutation(
                success=True,
                message="Empresa creada exitosamente",
                company=company,
                errors=[]
            )

        except Exception as e:
            return CreateCompanyMutation(
                success=False,
                message="Error interno del servidor",
                errors=[str(e)]
            )


class UpdateCompanyMutation(graphene.Mutation):
    """
    Actualizar empresa existente con validaciones completas
    """

    class Arguments:
        company_id = graphene.Int(required=True)
        ruc = graphene.String()
        denomination = graphene.String()
        address = graphene.String()
        phone = graphene.String()
        email = graphene.String()
        current_password = graphene.String()
        new_password = graphene.String()
        logo_base64 = graphene.String()
        remove_logo = graphene.Boolean()
        igv_percentage = graphene.Int()
        pdf_size = graphene.String()
        pdf_color = graphene.String()
        is_active = graphene.Boolean()

    # Respuesta
    success = graphene.Boolean()
    message = graphene.String()
    company = graphene.Field(CompanyType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, company_id, **kwargs):
        errors = []

        try:
            # Buscar la empresa
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                return UpdateCompanyMutation(
                    success=False,
                    message="Empresa no encontrada",
                    errors=["La empresa especificada no existe"]
                )

            # Validar RUC si se proporciona
            ruc = kwargs.get('ruc')
            if ruc is not None:
                if not ruc or len(ruc) != 11 or not ruc.isdigit():
                    errors.append("RUC debe tener 11 dígitos numéricos")
                elif ruc != company.ruc and Company.objects.filter(ruc=ruc).exists():
                    errors.append("Ya existe otra empresa con este RUC")

            # Validar denominación si se proporciona
            denomination = kwargs.get('denomination')
            if denomination is not None:
                if not denomination or len(denomination.strip()) < 3:
                    errors.append("La razón social debe tener al menos 3 caracteres")
                elif len(denomination) > 150:
                    errors.append("La razón social no puede exceder 150 caracteres")

            # Validar email si se proporciona
            email = kwargs.get('email')
            if email is not None:
                if not email:
                    errors.append("Email no puede estar vacío")
                else:
                    try:
                        validate_email(email)
                    except ValidationError:
                        errors.append("Formato de email inválido")

                    # Verificar si email ya existe en otra empresa
                    if email.lower() != company.email.lower() and Company.objects.filter(email__iexact=email).exists():
                        errors.append("Ya existe otra empresa con este email")

            # Validar cambio de contraseña
            current_password = kwargs.get('current_password')
            new_password = kwargs.get('new_password')

            if new_password is not None:
                if not current_password:
                    errors.append("Debe proporcionar la contraseña actual para cambiarla")
                elif not company.check_password(current_password):
                    errors.append("Contraseña actual incorrecta")
                elif len(new_password) < 6:
                    errors.append("La nueva contraseña debe tener al menos 6 caracteres")
                elif len(new_password) > 128:
                    errors.append("La nueva contraseña no puede exceder 128 caracteres")

            # Validar dirección si se proporciona
            address = kwargs.get('address')
            if address is not None and len(address) > 200:
                errors.append("La dirección no puede exceder 200 caracteres")

            # Validar teléfono si se proporciona
            phone = kwargs.get('phone')
            if phone is not None:
                if phone and not re.match(r'^[\d\s\-\(\)\+]+$', phone):
                    errors.append("Formato de teléfono inválido")
                elif phone and len(phone) > 45:
                    errors.append("El teléfono no puede exceder 45 caracteres")

            # Validar IGV si se proporciona
            igv_percentage = kwargs.get('igv_percentage')
            if igv_percentage is not None:
                valid_igv_values = [18, 10, 4]
                if igv_percentage not in valid_igv_values:
                    errors.append("IGV debe ser 18%, 10% o 4%")

            # Validar tamaño PDF si se proporciona
            pdf_size = kwargs.get('pdf_size')
            if pdf_size is not None:
                valid_pdf_sizes = ['T', 'A']
                if pdf_size not in valid_pdf_sizes:
                    errors.append("Tamaño de PDF debe ser 'T' (Ticket) o 'A' (A4)")

            # Validar color PDF si se proporciona
            pdf_color = kwargs.get('pdf_color')
            if pdf_color is not None:
                if not re.match(r'^#[0-9A-Fa-f]{6}$', pdf_color):
                    errors.append("Color PDF debe estar en formato hexadecimal (#RRGGBB)")

            # Validar logo si se proporciona
            logo_base64 = kwargs.get('logo_base64')
            logo_file = None
            if logo_base64:
                try:
                    # Remover prefijo data:image si existe
                    if logo_base64.startswith('data:image'):
                        logo_base64 = logo_base64.split(',')[1]

                    # Decodificar base64
                    logo_data = base64.b64decode(logo_base64)

                    # Validar tamaño (máximo 5MB)
                    if len(logo_data) > 5 * 1024 * 1024:
                        errors.append("El logo no puede exceder 5MB")
                    else:
                        logo_file = ContentFile(logo_data, name=f"logo_{company.ruc}.png")

                except Exception as e:
                    errors.append("Error al procesar el logo: formato base64 inválido")

            if errors:
                return UpdateCompanyMutation(
                    success=False,
                    message="Datos inválidos",
                    errors=errors
                )

            # Actualizar campos si se proporcionan
            if ruc is not None:
                company.ruc = ruc
            if denomination is not None:
                company.denomination = denomination.strip()
            if address is not None:
                company.address = address.strip()
            if phone is not None:
                company.phone = phone.strip()
            if email is not None:
                company.email = email.lower().strip()
            if new_password is not None:
                company.set_password(new_password)
            if igv_percentage is not None:
                company.igv_percentage = igv_percentage
            if pdf_size is not None:
                company.pdf_size = pdf_size
            if pdf_color is not None:
                company.pdf_color = pdf_color

            # Manejar estado activo
            is_active = kwargs.get('is_active')
            if is_active is not None:
                company.is_active = is_active

            # Manejar logo
            remove_logo = kwargs.get('remove_logo', False)
            if remove_logo:
                if company.logo:
                    # Eliminar archivo anterior
                    if os.path.isfile(company.logo.path):
                        os.remove(company.logo.path)
                    company.logo = None
            elif logo_file:
                # Eliminar logo anterior si existe
                if company.logo and os.path.isfile(company.logo.path):
                    os.remove(company.logo.path)
                company.logo = logo_file

            # Guardar cambios
            company.save()

            return UpdateCompanyMutation(
                success=True,
                message="Empresa actualizada exitosamente",
                company=company,
                errors=[]
            )

        except Exception as e:
            return UpdateCompanyMutation(
                success=False,
                message="Error interno del servidor",
                errors=[str(e)]
            )