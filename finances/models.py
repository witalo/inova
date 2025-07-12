from django.db import models
from django.utils import timezone

class Payment(models.Model):
    # Tipos de pago
    PAYMENT_TYPES = [
        ('CN', 'CONTADO'),
        ('CR', 'CRÉDITO'),
    ]
    # Métodos de pago para contado
    PAYMENT_METHODS = [
        ('E', 'EFECTIVO'),
        ('Y', 'YAPE'),
        ('P', 'PLIN'),
        ('T', 'TARJETA'),
        ('B', 'TRANSFERENCIA/DEPÓSITO')
    ]
    # Estados de pago
    STATUS_CHOICES = [
        ('P', 'PENDIENTE'),
        ('C', 'CANCELADO'),
    ]
    TYPE_CHOICES = [
        ('I', 'INGRESO'),
        ('E', 'EGRESO'),
    ]
    id = models.AutoField(primary_key=True)
    payment_type = models.CharField(max_length=2, choices=PAYMENT_TYPES, default='CN')
    payment_method = models.CharField(max_length=1, choices=PAYMENT_METHODS, default='A')
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='C')
    type = models.CharField(max_length=1, choices=TYPE_CHOICES, default='I')
    notes = models.TextField(blank=True, null=True, verbose_name="Notas")
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True)
    operation = models.ForeignKey('operations.Operation', on_delete=models.CASCADE, null=True, blank=True)
    company = models.ForeignKey('users.Company', on_delete=models.SET_NULL, null=True, blank=True)
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="Fecha")
    total_amount = models.DecimalField(max_digits=15, decimal_places=6, default=0, verbose_name="Monto total")
    paid_amount = models.DecimalField(max_digits=15, decimal_places=6, default=0, verbose_name="Monto pagado")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.payment_date} {self.paid_amount}'

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'