from django.contrib import admin

# Register your models here.
from users.models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django import forms


class CompanyAdmin(admin.ModelAdmin):
    list_display = ('denomination', 'ruc', 'email', 'is_active')

    def save_model(self, request, obj, form, change):
        # Si el campo password está siendo modificado o es un nuevo registro
        if 'password' in form.changed_data or not change:
            if obj.password:  # Si hay una contraseña proporcionada
                # Encripta la contraseña solo si no está ya encriptada
                if not obj.password.startswith('pbkdf2_sha256$'):
                    obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)


admin.site.register(Company, CompanyAdmin)


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
