import graphene

from users.models import User


class CreateUserMutation(graphene.Mutation):
    class Arguments:
        first_name = graphene.String()
        last_name = graphene.String()
        names = graphene.String()
        document = graphene.String()
        phone = graphene.String()
        password = graphene.String()
        email = graphene.String()
        is_active = graphene.Boolean()

    message = graphene.String()

    @staticmethod
    def mutate(self, info,
               first_name, last_name, document, phone, password, email, is_active):
        user_obj = User(
            first_name=str(first_name).upper(),
            last_name=str(last_name).upper(),
            document=document,
            phone=phone,
            username=email,
            email=email,
            is_active=is_active
        )
        user_obj.set_password(password)
        user_obj.save()
        return CreateUserMutation(message='Usuario registrado.')


class UpdateUserMutation(graphene.Mutation):
    class Arguments:
        id = graphene.ID(required=True)
        first_name = graphene.String()
        last_name = graphene.String()
        document = graphene.String()
        phone = graphene.String()
        password = graphene.String()
        email = graphene.String()
        is_active = graphene.Boolean()

    message = graphene.String()

    @staticmethod
    def mutate(self, info, id, first_name, last_name, document, phone, password, email, is_active):
        user_obj = User.objects.get(pk=id)
        user_obj.first_name = str(first_name).upper()
        user_obj.last_name = str(last_name).upper()
        user_obj.document = document
        user_obj.phone = phone
        user_obj.username = email
        user_obj.email = email
        user_obj.is_active = is_active
        if len(password) > 0 and password != 'undefined':
            print('change password', password)
            user_obj.set_password(password)
        user_obj.save()
        return UpdateUserMutation(message='Usuario actualizado.')
