from django.contrib import admin

# Register your models here.
from finances.models import *


# admin.site.register(Payment)
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'operation',
        'payment_type',
        'payment_method',
        'status',
        'payment_date',
        'paid_amount',
        'created_at'
    ]
    list_filter = [
        'payment_type',
        'payment_method',
        'status',
        'payment_date',
        'company'
    ]
    search_fields = [
        'operation__serial',
        'operation__number',
        'notes'
    ]
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('operation', 'user', 'company')
