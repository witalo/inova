import os

from django.contrib.auth.models import AbstractUser
from django.db import models

PDF_SIZES = [
    ('T', 'Ticket'),
    ('A', 'A4'),
]

IGV_PERCENTAGES = [
    (18, '18%'),
    (10, '10%'),
    (4, '4%'),
]


class Company(models.Model):
    id = models.AutoField(primary_key=True)
    ruc = models.CharField(max_length=11, null=True, blank=True)
    denomination = models.CharField('Razón social', max_length=150, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=45, null=True, blank=True)
    email = models.EmailField(max_length=45, null=True, blank=True)
    logo = models.ImageField('Logo', upload_to='companies/', blank=True, null=True)
    igv_percentage = models.IntegerField('IGV (%)', choices=IGV_PERCENTAGES, default=18)
    pdf_size = models.CharField('Tamaño PDF', max_length=10, choices=PDF_SIZES, default='TICKET')
    pdf_color = models.CharField('Color PDF', max_length=7, default='#000000')  # Example: #FF5733
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.denomination

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'


class User(AbstractUser):
    dni = models.CharField('Numero documento', max_length=8, null=True, blank=True)
    phone = models.CharField('Celular', max_length=9, null=True, blank=True)
    photo = models.ImageField('Foto', upload_to='users/', blank=True, null=True)
    company = models.ForeignKey('Company', on_delete=models.SET_NULL, null=True, blank=True)

    REQUIRED_FIELDS = ['email', 'dni', 'first_name', 'last_name']

    def save(self, *args, **kwargs):
        try:
            # Obtén el usuario actual antes de guardarlo
            old_user = User.objects.get(pk=self.pk)
            if old_user.photo and old_user.photo != self.photo:
                # Si existe una foto anterior y es diferente a la nueva, elimínala
                if os.path.isfile(old_user.photo.path):
                    os.remove(old_user.photo.path)
        except User.DoesNotExist:
            # Si el usuario no existe, no hagas nada
            pass
        super(User, self).save(*args, **kwargs)

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['id']

    def __str__(self):
        return self.email
