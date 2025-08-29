import graphene
from graphene_django import DjangoObjectType

from finances.models import Payment


class PaymentType(DjangoObjectType):
    class Meta:
        model = Payment
        fields = "__all__"


class PaymentInput(graphene.InputObjectType):
    id = graphene.Int()
    type = graphene.String(default="I")
    payment_type = graphene.String(required=True)
    payment_method = graphene.String(required=True)
    status = graphene.String(default="C")
    notes = graphene.String()
    payment_date = graphene.String(default=0)
    total_amount = graphene.Float(default=0)
    paid_amount = graphene.Float(required=True)
    user_id = graphene.Int()
    company_id = graphene.Int()
    operation_id = graphene.Int()


class UpdatePaymentInput(graphene.InputObjectType):
    status = graphene.String()
    notes = graphene.String()
    paid_amount = graphene.Float()


# Reporte mensual
class MonthlySummaryType(graphene.ObjectType):
    # Operaciones
    total_entrada = graphene.Float()
    total_salida = graphene.Float()
    gross_profit_operations = graphene.Float()

    # Pagos
    total_ingresos = graphene.Float()
    total_egresos = graphene.Float()
    cash_flow = graphene.Float()

    # Campos existentes (mantener)
    total_operations = graphene.Float()
    total_payments = graphene.Float()
    gross_profit = graphene.Float()
    operation_count = graphene.Int()
    payment_count = graphene.Int()
    average_daily_operations = graphene.Float()
    average_daily_payments = graphene.Float()


class OperationsByDocumentType(graphene.ObjectType):
    document_id = graphene.Int()
    document_name = graphene.String()
    total_amount = graphene.Float()
    operation_count = graphene.Int()
    average_amount = graphene.Float()


class PaymentsByMethodType(graphene.ObjectType):
    method = graphene.String()
    total_amount = graphene.Float()
    transaction_count = graphene.Int()
    percentage = graphene.Float()
    type = graphene.String()  # NUEVO: "INGRESO" o "EGRESO"
    method_code = graphene.String()  # NUEVO: "E", "Y", "P", "T", "B"


class DailyDataType(graphene.ObjectType):
    day = graphene.Int()
    entrada_amount = graphene.Float()  # NUEVO
    salida_amount = graphene.Float()  # NUEVO
    operations_amount = graphene.Float()  # NUEVO (neto)
    ingresos_amount = graphene.Float()  # NUEVO
    egresos_amount = graphene.Float()  # NUEVO
    payments_amount = graphene.Float()  # NUEVO (neto)


class PaymentMonthlyReportType(graphene.ObjectType):
    summary = graphene.Field(MonthlySummaryType)
    operations_by_document = graphene.List(OperationsByDocumentType)
    payments_by_method = graphene.List(PaymentsByMethodType)
    daily_data = graphene.List(DailyDataType)
