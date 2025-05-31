import base64
import graphene
from django.contrib.auth import authenticate
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
