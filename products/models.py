from django.db import models


# Create your models here.
class TypeAffectation(models.Model):
    code = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Tipo de afectación'
        verbose_name_plural = 'Tipos de afectación'


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=20, null=True, blank=True)
    code_snt = models.CharField(max_length=20, null=True, blank=True)
    description = models.CharField(max_length=500, null=True, blank=True)
    price_without_igv = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    price_with_igv = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    stock = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    type_affectation = models.ForeignKey('TypeAffectation', on_delete=models.SET_NULL, null=True, blank=True)
    unit = models.ForeignKey('Unit', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return str(self.description)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'


class Unit(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return str(self.description)

    class Meta:
        verbose_name = 'Unidad'
        verbose_name_plural = 'Unidades'
