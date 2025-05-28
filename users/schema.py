from datetime import datetime

import graphql_jwt
from django.core.exceptions import ValidationError

from users.models import User
from users.mutations import *
from users.types import *


class UsersQuery(graphene.ObjectType):
    # Queries para usuarios
    user_by_id = graphene.Field(UserType, pk=graphene.ID())
    users_by_company = graphene.List(UserType, company_id=graphene.ID())
    me = graphene.Field(UserType)

    # Queries para empresas
    company_by_id = graphene.Field(CompanyType, pk=graphene.ID())
    company_by_ruc = graphene.Field(CompanyType, ruc=graphene.String())

    @staticmethod
    def resolve_user_by_id(root, info, pk):
        try:
            return User.objects.get(pk=pk)
        except User.DoesNotExist:
            return None

    @staticmethod
    def resolve_users_by_company(root, info, company_id):
        return User.objects.filter(company_id=company_id, is_active=True)

    @staticmethod
    def resolve_me(root, info):
        user = info.context.user
        if user.is_authenticated:
            return user
        return None

    @staticmethod
    def resolve_company_by_id(root, info, pk):
        try:
            return Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return None

    @staticmethod
    def resolve_company_by_ruc(root, info, ruc):
        try:
            return Company.objects.get(ruc=ruc)
        except Company.DoesNotExist:
            return None


class UsersMutation(graphene.ObjectType):
    # Autenticación JWT estándar
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()

    # Nuestras mutaciones personalizadas
    company_login = CompanyLoginMutation.Field()
    user_login = UserLoginMutation.Field()
    create_user = CreateUserMutation.Field()
    update_user = UpdateUserMutation.Field()
