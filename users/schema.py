from datetime import datetime

import graphql_jwt
from django.core.exceptions import ValidationError

from users.models import User
from users.mutations import *
from users.types import *


class UsrQuery(graphene.ObjectType):
    user_by_id = graphene.Field(UserType, pk=graphene.ID())

    @staticmethod
    def resolve_user_by_id(self, info, pk):
        return User.objects.get(pk=pk)


class UsrMutation(graphene.ObjectType):
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()
    create_user = CreateUserMutation.Field()
    update_user = UpdateUserMutation.Field()

