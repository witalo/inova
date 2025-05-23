from django.contrib import admin

# Register your models here.
from products.models import Product, TypeAffectation, Unit

admin.site.register(Product)
admin.site.register(TypeAffectation)
admin.site.register(Unit)