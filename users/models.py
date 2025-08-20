import os

from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import AbstractUser
from django.db import models

from operations.services.billing_service import BillingFileManager

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
    ruc = models.CharField(max_length=11, unique=True, null=True, blank=True)
    denomination = models.CharField('Razón social', max_length=150, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=45, null=True, blank=True)
    email = models.EmailField(max_length=45, unique=True, null=True, blank=True)
    password = models.CharField('Contraseña', max_length=128, null=True, blank=True)
    logo = models.ImageField('Logo', upload_to='companies/', blank=True, null=True)
    igv_percentage = models.IntegerField('IGV (%)', choices=IGV_PERCENTAGES, default=18)
    pdf_size = models.CharField('Tamaño PDF', max_length=10, choices=PDF_SIZES, default='T')
    pdf_color = models.CharField('Color PDF', max_length=7, default='#000000')
    is_active = models.BooleanField('Activo', default=True)
    is_payment = models.BooleanField('Activar Pago', default=False)
    is_billing = models.BooleanField('Activar Facturacion', default=False)

    # NUEVOS CAMPOS MÍNIMOS NECESARIOS
    ubigeo = models.CharField(
        'Ubigeo',
        max_length=6,
        default='040101',
        help_text='Código de ubigeo según INEI (ej: 040101)'
    )

    department = models.CharField(
        'Departamento',
        max_length=100,
        default='AREQUIPA',
        help_text='Nombre del departamento'
    )

    province = models.CharField(
        'Provincia',
        max_length=100,
        default='AREQUIPA',
        help_text='Nombre de la provincia'
    )

    district = models.CharField(
        'Distrito',
        max_length=150,
        default='AREQUIPA',
        help_text='Nombre del distrito'
    )

    country_code = models.CharField(
        'Código de País',
        max_length=2,
        default='PE',
        help_text='Código ISO 3166-1 del país (PE)'
    )

    establishment_code = models.CharField(
        'Código de Establecimiento',
        max_length=4,
        default='0000',
        help_text='Código de establecimiento SUNAT'
    )

    # Configuración SUNAT
    environment = models.CharField(
        'Entorno SUNAT',
        max_length=20,
        choices=[
            ('BETA', 'Beta/Pruebas'),
            ('PRODUCTION', 'Producción'),
        ],
        default='BETA'
    )

    # Credenciales SUNAT
    sunat_username = models.CharField('Usuario SUNAT', max_length=100, null=True, blank=True)
    sunat_password = models.CharField('Contraseña SUNAT', max_length=150, null=True, blank=True)

    # Certificado digital
    certificate_path = models.CharField('Ruta Certificado', max_length=500, null=True, blank=True)
    private_key_path = models.CharField('Ruta Clave Privada', max_length=500, null=True, blank=True)
    certificate_password = models.CharField('Contraseña Certificado', max_length=100, null=True, blank=True)

    # Configuración adicional
    max_retry_attempts = models.IntegerField('Máximo Intentos', default=5)
    retry_interval_minutes = models.IntegerField('Intervalo Reintentos (min)', default=30)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_password(self, raw_password):
        """Encripta y guarda la contraseña"""
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Verifica la contraseña"""
        return check_password(raw_password, self.password)

    def save(self, *args, **kwargs):
        # Encriptar la contraseña si es nueva o se está modificando
        if not self.pk or 'password' in kwargs.get('update_fields', []):
            if self.password and not self.password.startswith('pbkdf2_sha256$'):
                self.password = make_password(self.password)

        # Manejo del logo
        try:
            old_company = Company.objects.get(pk=self.pk)
            if old_company.logo and old_company.logo != self.logo:
                if os.path.isfile(old_company.logo.path):
                    os.remove(old_company.logo.path)
        except Company.DoesNotExist:
            pass

        super().save(*args, **kwargs)
        # Crear estructura de carpetas al guardar
        if self.ruc:
            BillingFileManager.create_company_folders(self.ruc)

    def __str__(self):
        return self.denomination or f"Empresa {self.ruc}"

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['denomination']


class User(AbstractUser):
    dni = models.CharField('DNI', max_length=8, unique=True, null=True, blank=True)
    phone = models.CharField('Celular', max_length=9, null=True, blank=True)
    photo = models.ImageField('Foto', upload_to='users/', blank=True, null=True)
    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='users'
    )

    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    def save(self, *args, **kwargs):
        # Manejar eliminación de foto anterior si cambió
        if self.pk:
            try:
                old_user = User.objects.get(pk=self.pk)
                if old_user.photo and old_user.photo != self.photo:
                    # Si existe una foto anterior y es diferente, elimínala
                    if os.path.isfile(old_user.photo.path):
                        os.remove(old_user.photo.path)
            except User.DoesNotExist:
                pass

        super(User, self).save(*args, **kwargs)

    @property
    def full_name(self):
        """Retorna el nombre completo del usuario"""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def initials(self):
        """Retorna las iniciales del usuario"""
        first_initial = self.first_name[0] if self.first_name else ""
        last_initial = self.last_name[0] if self.last_name else ""
        return f"{first_initial}{last_initial}".upper()

    def __str__(self):
        return self.email or self.username

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['first_name', 'last_name']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['email']),
            models.Index(fields=['dni']),
        ]

    def __str__(self):
        return self.email or self.username
