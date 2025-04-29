import graphene
from graphene_django import DjangoObjectType

from users.models import User


class UserType(DjangoObjectType):
    id = graphene.Int()

    class Meta:
        model = User
        fields = '__all__'
