from django.contrib import admin

# Register your models here.
from users.models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django import forms


class CompanyAdminForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Dejar en blanco para mantener la contraseña actual"
    )

    class Meta:
        model = Company
        fields = '__all__'


class CompanyAdmin(admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ('denomination', 'ruc', 'email', 'is_active')

    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get('password')
        if password:  # Solo actualizar si se proporcionó una nueva contraseña
            obj.set_password(password)
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
