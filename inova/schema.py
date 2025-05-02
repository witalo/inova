import graphene
import graphql_jwt

from products.schema import ProductsQuery, ProductsMutation
from users.schema import UsersQuery, UsersMutation


class Query(UsersQuery, ProductsQuery):
    pass


class Mutation(UsersMutation, ProductsMutation):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
