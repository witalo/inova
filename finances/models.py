from django.db import models


# Create your models here.
class Cash(models.Model):
    ACCOUNT_TYPE_CHOICES = (('C', 'CAJA'), ('B', 'BANCO'))
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    account_number = models.CharField(max_length=50, null=True, blank=True)
    account_type = models.CharField(max_length=2, choices=ACCOUNT_TYPE_CHOICES, default='C')
    total = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    company = models.ForeignKey('users.Company', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name = 'Caja'
        verbose_name_plural = 'Cajas'


class Payment(models.Model):
    WAY_PAY_CHOICES = [
        (1, 'EFECTIVO [CONTADO]'),
        (2, 'POR PAGAR [CRÉDITO]')
    ]
    id = models.AutoField(primary_key=True)
    cash = models.ForeignKey('finances.Cash', on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)
    operation = models.ForeignKey('operations.Operation', on_delete=models.CASCADE, null=True, blank=True)
    transaction_date = models.DateField(null=True, blank=True)
    way_pay = models.IntegerField(choices=WAY_PAY_CHOICES, default=1)
    bank_operation_code = models.CharField(max_length=45, null=True, blank=True)
    description = models.CharField(max_length=200, null=True, blank=True)
    total = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_validated = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.transaction_date} {self.total}'

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'


class Quota(models.Model):
    id = models.AutoField(primary_key=True)
    payment_date = models.DateField(null=True, blank=True)
    number = models.IntegerField(default=1)
    total = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    payment = models.ForeignKey('finances.Payment', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.payment_date} {self.total}'

    class Meta:
        verbose_name = 'Cuota'
        verbose_name_plural = 'Cuotas'