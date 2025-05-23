from django.contrib import admin

# Register your models here.
from finances.models import *

admin.site.register(Cash)
admin.site.register(Payment)
admin.site.register(Quota)