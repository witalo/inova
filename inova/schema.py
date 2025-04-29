import graphene
import graphql_jwt

from users.schema import UsrQuery, UsrMutation


class Query(UsrQuery):
    pass


class Mutation(UsrMutation):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
