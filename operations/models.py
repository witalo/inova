from django.db import models


# Create your models here.
class Document(models.Model):
    id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=15, null=True, blank=True)
    description = models.CharField('Descripción', max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.description

    class Meta:
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'


class Serial(models.Model):
    id = models.AutoField(primary_key=True)
    serial = models.CharField('Descripción', max_length=100, null=True, blank=True)
    document = models.ForeignKey('Document', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.serial

    class Meta:
        verbose_name = 'Serie'
        verbose_name_plural = 'Series'


STATUS_CHOICES = [
    ('1', 'REGISTRADO'),  # BD
    ('2', 'EMITIDO'),  # ENVIADO GENERO CDR
    ('3', 'PENDIENTE DE BAJA'),  # BOL/FACT/NOT CRE
    ('4', 'EN PROCESO DE BAJA'),  # BOL/FACT/NOT CRE
    ('5', 'DADO DE BAJA'),
    ('6', 'RECHAZADO')
]
OPERATION_TYPE_CHOICES = [
    ('E', 'ENTRADA'),
    ('S', 'SALIDA')
]
CURRENCY_TYPE_CHOICES = [
    ("PEN", 'SOLES'),
    ("USD", 'DÓLARES')
]


class Operation(models.Model):
    id = models.AutoField(primary_key=True)
    document = models.ForeignKey('Document', on_delete=models.SET_NULL, null=True, blank=True)
    operation_type = models.CharField('TIPO DE OPERACION', max_length=1, choices=OPERATION_TYPE_CHOICES, default='NA')
    operation_status = models.CharField('ESTADO', max_length=1, choices=STATUS_CHOICES, default='1')
    serial = models.CharField(verbose_name='SERIE', max_length=4, null=True, blank=True)
    number = models.IntegerField(verbose_name='NUMERO', null=True, blank=True)
    currency = models.CharField('MONEDA', max_length=3, choices=CURRENCY_TYPE_CHOICES, default='PEN')
    sell_rate = models.DecimalField('VALOR CAMBIO VENTA', max_digits=10, decimal_places=6, default=0)
    buy_rate = models.DecimalField('VALOR CAMBIO COMPRA', max_digits=10, decimal_places=6, default=0)
    operation_date = models.DateField(null=True, blank=True)
    emit_date = models.DateField(null=True, blank=True)
    emit_time = models.TimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    low_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    person = models.ForeignKey('operations.Person', on_delete=models.SET_NULL, null=True, blank=True)
    company = models.ForeignKey('users.Company', on_delete=models.SET_NULL, null=True, blank=True)

    items_total_discount = models.DecimalField('DESCUENTO POR ITEM', max_digits=15, decimal_places=6, default=0)
    global_discount = models.DecimalField('DESCUENTO GLOBAL', max_digits=15, decimal_places=6, default=0)
    global_discount_percent = models.DecimalField('PORCENTAJE DESCUENTO GLOBAL', max_digits=15, decimal_places=6,
                                                  default=0)
    total_discount = models.DecimalField('TOTAL DESCUENTO', max_digits=15, decimal_places=6, default=0)

    igv_percent = models.DecimalField('PORCENTAJE IGV', max_digits=15, decimal_places=6, default=18)
    igv_amount = models.DecimalField('TOTAL IGV', max_digits=15, decimal_places=6, default=0)

    total_taxable = models.DecimalField('TOTAL GRAVADA', max_digits=15, decimal_places=6, default=0)
    total_unaffected = models.DecimalField('TOTAL INAFECTA', max_digits=15, decimal_places=6, default=0)
    total_exempt = models.DecimalField('TOTAL EXONERADA', max_digits=15, decimal_places=6, default=0)
    total_free = models.DecimalField('TOTAL GRATUITA', max_digits=15, decimal_places=6, default=0)
    total_amount = models.DecimalField('TOTAL IMPORTE', max_digits=15, decimal_places=6, default=0)

    send_sunat = models.BooleanField(default=False)
    send_person = models.BooleanField(default=False)
    sunat_description = models.CharField(verbose_name='DESCRIPCION SUNAT', max_length=300, null=True, blank=True)
    sunat_description_low = models.CharField(verbose_name='DESCRIPCION SUNAT BAJA', max_length=300, null=True,
                                             blank=True)
    sunat_status = models.BooleanField(default=False)
    parent_operation = models.ForeignKey('Operation', on_delete=models.SET_NULL, null=True, blank=True)

    link_xml = models.CharField('ENLACE XML', max_length=900, null=True, blank=True)
    link_cdr = models.CharField('ENLACE CDR', max_length=900, null=True, blank=True)
    low_number = models.IntegerField(verbose_name='NUMERO ANULACION', null=True, blank=True)
    summary_number = models.IntegerField(verbose_name='NUMERO RESUMEN', null=True, blank=True)
    low_ticket = models.CharField('TICKET ANULACION', max_length=100, null=True, blank=True)
    link_xml_low = models.CharField('ENLACE XML DE BAJA', max_length=900, null=True, blank=True)
    link_cdr_low = models.CharField('ENLACE CDR DE BAJA', max_length=900, null=True, blank=True)

    code_hash = models.CharField('CODIGO HASH', max_length=900, null=True, blank=True)

    class Meta:
        verbose_name = 'Operacion'
        verbose_name_plural = 'Operaciones'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'operation_date', 'total_amount', 'person'],
                name='unique_operation'
            )
        ]

    def __str__(self):
        return f"{self.serial}-{self.number}"


class OperationDetail(models.Model):
    id = models.AutoField(primary_key=True)
    operation = models.ForeignKey('operations.Operation', on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField('Descripcion', max_length=500, null=True, blank=True)
    type_affectation = models.ForeignKey('products.TypeAffectation', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    unit_value = models.DecimalField('Valor unitario', max_digits=15, decimal_places=6, default=0)
    unit_price = models.DecimalField('Precio unitario', max_digits=15, decimal_places=6, default=0)
    # %discount_percentage = total_discount / (unit_value * quantity)
    discount_percentage = models.DecimalField('Porcentaje de descuento', max_digits=15, decimal_places=6, default=0)
    # total_discount = unit_value * quantity * %discount_percentage
    total_discount = models.DecimalField('Descuento total', max_digits=15, decimal_places=6, default=0)
    # total_value = unit_value * quantity - total_discount
    total_value = models.DecimalField('Valor total', max_digits=15, decimal_places=6, default=0)
    # total_igv = total_value * %igv_percentage
    total_igv = models.DecimalField('Igv total', max_digits=15, decimal_places=6, default=0)
    # total_amount = total_value + total_igv
    total_amount = models.DecimalField('Importe total', max_digits=15, decimal_places=6, default=0)
    remaining_quantity = models.DecimalField(max_digits=20, decimal_places=6, default=0)

    class Meta:
        verbose_name = 'Detalle operacion'
        verbose_name_plural = 'Detalles operaciones'
        ordering = ['id']

    def __str__(self):
        return str(self.id)
