from django.contrib import admin

# Register your models here.
from users.models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

admin.site.register(Company)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'first_name',
                    'last_name', 'is_superuser', 'is_staff', 'date_joined']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': (
            'dni', 'first_name', 'last_name', 'email', 'phone', 'photo', 'company')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'user_permissions'), }),

        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),)
    readonly_fields = ['date_joined', 'last_login']
