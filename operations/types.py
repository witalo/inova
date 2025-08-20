import graphene
from django.db.models import Prefetch
from graphene_django import DjangoObjectType

from finances.types import PaymentType
from operations.models import Person, Document, Serial, Operation, OperationDetail
from products.models import Product, Unit
from products.types import TopProductType


class PersonInput(graphene.InputObjectType):
    id = graphene.ID(description="ID solo para actualización")
    person_type = graphene.String(required=True, description="Tipo de documento: 1 (DNI) o 6 (RUC)")
    person_number = graphene.String(required=True, description="Número de documento (8 dígitos para DNI, 11 para RUC)")
    full_name = graphene.String(required=True, description="Nombre completo")
    is_customer = graphene.Boolean(description="¿Es cliente? (default=False)")
    is_supplier = graphene.Boolean(description="¿Es proveedor? (default=False)")
    address = graphene.String(description="Dirección completa")
    phone = graphene.String(description="Teléfono (opcional)")
    email = graphene.String(description="Email (opcional, validado)")


class DocumentType(DjangoObjectType):
    class Meta:
        model = Document
        fields = '__all__'


class SerialType(DjangoObjectType):
    class Meta:
        model = Serial
        fields = '__all__'


class PersonType(DjangoObjectType):
    id = graphene.Int()

    class Meta:
        model = Person
        fields = '__all__'


class OperationType(DjangoObjectType):
    id = graphene.Int()
    details = graphene.List(lambda: OperationDetailType)
    # Campos obligatorios con valores por defecto
    total_discount = graphene.Float(required=True)
    igv_percent = graphene.Float(required=True)
    igv_amount = graphene.Float(required=True)
    total_taxable = graphene.Float(required=True)
    total_unaffected = graphene.Float(required=True)
    total_exempt = graphene.Float(required=True)
    total_free = graphene.Float(required=True)
    total_amount = graphene.Float(required=True)
    global_discount = graphene.Float(required=True)
    global_discount_percent = graphene.Float(required=True)
    payment_set = graphene.List(PaymentType)

    xml_download_url = graphene.String()
    signed_xml_download_url = graphene.String()
    cdr_download_url = graphene.String()
    cancellation_xml_download_url = graphene.String()
    cancellation_signed_xml_download_url = graphene.String()
    cancellation_cdr_download_url = graphene.String()

    class Meta:
        model = Operation
        fields = '__all__'

    def resolve_details(self, info):
        return self.operationdetail_set.all()

    def resolve_payment_set(self, info):
        return self.payment_set.all()

    def resolve_xml_download_url(self, info):
        return self.xml_download_url

    def resolve_signed_xml_download_url(self, info):
        return self.signed_xml_download_url

    def resolve_cdr_download_url(self, info):
        return self.cdr_download_url

    def resolve_cancellation_xml_download_url(self, info):
        return self.cancellation_xml_download_url

    def resolve_cancellation_signed_xml_download_url(self, info):
        return self.cancellation_signed_xml_download_url

    def resolve_cancellation_cdr_download_url(self, info):
        return self.cancellation_cdr_download_url


class OperationDetailType(DjangoObjectType):
    id = graphene.Int()
    quantity = graphene.Float()
    unit_value = graphene.Float()
    unit_price = graphene.Float()
    total_discount = graphene.Float()
    total_value = graphene.Float()
    total_igv = graphene.Float()
    total_amount = graphene.Float()

    class Meta:
        model = OperationDetail
        fields = '__all__'


# Types para resumen
class SalesSummaryType(graphene.ObjectType):
    total_sales = graphene.Int()
    total_amount = graphene.Float()
    total_igv = graphene.Float()
    total_discount = graphene.Float()
    average_ticket = graphene.Float()
    top_products = graphene.List(TopProductType)


# Input Types
class OperationDetailInput(graphene.InputObjectType):
    product_id = graphene.ID(required=True)
    quantity = graphene.Float(required=True)
    unit_value = graphene.Float(required=True)
    unit_price = graphene.Float(required=True)
    discount_percentage = graphene.Float(default_value=0)
    type_affectation_id = graphene.ID(required=True)


# Types para el reporte
class DailyOperationType(graphene.ObjectType):
    day = graphene.Int()
    date = graphene.String()
    total_sales = graphene.Float()
    total_purchases = graphene.Float()
    sales_count = graphene.Int()
    purchases_count = graphene.Int()


class MonthlyReportType(graphene.ObjectType):
    daily_operations = graphene.List(DailyOperationType)
    top_products = graphene.List(TopProductType)
    total_transactions = graphene.Int()
    total_sales = graphene.Float()
    total_purchases = graphene.Float()
    total_profit = graphene.Float()


class SoldProductType(graphene.ObjectType):
    product_id = graphene.Int()
    product_name = graphene.String()
    product_code = graphene.String()
    quantity = graphene.Float()
    unit = graphene.String()
    unit_price = graphene.Float()
    total = graphene.Float()
    timestamp = graphene.String()
    operation_id = graphene.Int()


class HourlySalesType(graphene.ObjectType):
    hour = graphene.Int()
    sales_amount = graphene.Float()
    sales_count = graphene.Int()


class DailyReportType(graphene.ObjectType):
    total_sales = graphene.Float()
    total_purchases = graphene.Float()
    sales_count = graphene.Int()
    purchases_count = graphene.Int()
    sales_growth = graphene.Float()
    last_sold_products = graphene.List(SoldProductType)
    hourly_sales = graphene.List(HourlySalesType)
    top_selling_hour = graphene.String()


class DailySummaryType(graphene.ObjectType):
    total_sales = graphene.Float()
    total_purchases = graphene.Float()
    sales_count = graphene.Int()
    purchases_count = graphene.Int()
    balance = graphene.Float()
    average_ticket = graphene.Float()


# Types
class DailyReportsType(graphene.ObjectType):
    date = graphene.String()
    entries = graphene.Int()
    entries_amount = graphene.Float()
    sales = graphene.Int()
    sales_amount = graphene.Float()
    profit = graphene.Float()
    transaction_count = graphene.Int()


class ProductReportType(graphene.ObjectType):
    product_id = graphene.ID()
    product_name = graphene.String()
    product_code = graphene.String()
    quantity_sold = graphene.Float()
    quantity_purchased = graphene.Float()
    total_sales = graphene.Float()
    total_purchases = graphene.Float()
    profit = graphene.Float()
    stock_movement = graphene.Float()


class StatsType(graphene.ObjectType):
    total_entries = graphene.Int()
    total_entries_amount = graphene.Float()
    total_sales = graphene.Int()
    total_sales_amount = graphene.Float()
    total_profit = graphene.Float()
    avg_daily_sales = graphene.Float()
    avg_daily_entries = graphene.Float()
    growth_rate = graphene.Float()


class PaymentMethodType(graphene.ObjectType):
    method = graphene.String()
    method_name = graphene.String()
    count = graphene.Int()
    amount = graphene.Float()
    percentage = graphene.Float()


class TopCustomerType(graphene.ObjectType):
    customer_id = graphene.ID()
    customer_name = graphene.String()
    customer_document = graphene.String()
    purchase_count = graphene.Int()
    total_amount = graphene.Float()
    avg_ticket = graphene.Float()
    last_purchase = graphene.String()


class MonthlyReportsType(graphene.ObjectType):
    daily_reports = graphene.List(DailyReportsType)
    product_reports = graphene.List(ProductReportType)
    stats = graphene.Field(StatsType)
    payment_methods = graphene.List(PaymentMethodType)
    top_customers = graphene.List(TopCustomerType)
