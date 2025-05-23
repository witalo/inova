from django.contrib import admin

# Register your models here.
from operations.models import *

admin.site.register(Serial)
admin.site.register(Document)
admin.site.register(Operation)
admin.site.register(OperationDetail)
admin.site.register(Person)