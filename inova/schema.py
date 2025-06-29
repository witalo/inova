import graphene
import graphql_jwt

from finances.schema import FinancesQuery, FinancesMutation
from operations.schema import OperationsQuery, OperationsMutation
from products.schema import ProductsQuery, ProductsMutation
from users.schema import UsersQuery, UsersMutation


class Query(UsersQuery, ProductsQuery, OperationsQuery, FinancesQuery):
    pass


class Mutation(UsersMutation, ProductsMutation, OperationsMutation, FinancesMutation):
    pass


schema = graphene.Schema(query=Query, mutation=Mutation)
