import warnings
from calendar import monthrange
from datetime import datetime, timedelta, time

import graphene
from django.db.models import Sum

from finances.models import Payment
from finances.mutations import CreatePayment, UpdatePayment, DeletePayment, CancelPayment
from finances.types import PaymentType, PaymentMonthlyReportType
import pytz
from django.utils import timezone

# Definir la zona horaria de Perú
from operations.models import Document, Operation

peru_tz = pytz.timezone('America/Lima')


class FinancesQuery(graphene.ObjectType):
    # Obtener pagos por fecha y compañía
    payments_by_date = graphene.List(
        PaymentType,
        company_id=graphene.Int(required=True),
        date=graphene.String(required=True)
    )

    # Obtener un pago por ID
    payment = graphene.Field(PaymentType, id=graphene.Int(required=True))

    # Obtener resumen financiero por fecha
    financial_summary = graphene.Field(
        graphene.Float,
        company_id=graphene.Int(required=True),
        date=graphene.String(required=True),
        summary_type=graphene.String(required=True)  # 'income', 'expense', 'balance'
    )

    payment_monthly_report = graphene.Field(
        PaymentMonthlyReportType,
        company_id=graphene.Int(required=True),
        year=graphene.Int(required=True),
        month=graphene.Int(required=True)
    )

    @staticmethod
    def resolve_payments_by_date(self, info, company_id, date):
        try:
            from django.utils import timezone
            from datetime import timedelta

            # 1. Depuración inicial
            print(f"Buscando pagos para company_id={company_id}, date={date}")

            # ✅ CORREGIDO: Convertir fecha con zona horaria de Perú
            naive_date = datetime.strptime(date, '%Y-%m-%d').date()
            start_date = timezone.make_aware(
                datetime.combine(naive_date, datetime.min.time()),
                timezone=peru_tz
            )
            end_date = start_date + timedelta(days=1)

            # ✅ DEBUG: Prints para verificar rangos de fecha
            print(f"Start date (Perú): {start_date}")
            print(f"Start date (UTC): {start_date.astimezone(pytz.UTC)}")
            print(f"End date (Perú): {end_date}")
            print(f"End date (UTC): {end_date.astimezone(pytz.UTC)}")

            # 3. Consulta: mostrar todos los pagos (incl. anulados); totales usan is_enabled en otro query
            payments = Payment.objects.filter(
                company_id=company_id,
                payment_date__gte=start_date,
                payment_date__lt=end_date
            ).select_related('user', 'company', 'operation').order_by('-payment_date')

            # ✅ CORREGIDO: Convertir fechas de pagos a zona horaria de Perú para mostrar
            payments_list = list(payments)
            for payment in payments_list:
                payment.payment_date = payment.payment_date.astimezone(peru_tz)
                print(f"Pago ID {payment.id}: {payment.payment_date} (Perú)")

            # 4. Depuración de resultados
            print(f"Pagos encontrados: {len(payments_list)}")

            return payments_list

        except Exception as e:
            import traceback
            traceback.print_exc()
            raise Exception(f"Error al obtener pagos: {str(e)}")

    @staticmethod
    def resolve_payment(self, info, id):
        try:
            # Permitir consultar también pagos anulados (para mostrarlos en lista)
            payment = Payment.objects.get(pk=id)
            # ✅ CORREGIDO: Convertir fecha a zona horaria de Perú
            payment.payment_date = payment.payment_date.astimezone(peru_tz)
            return payment
        except Payment.DoesNotExist:
            raise Exception("Pago no encontrado")

    @staticmethod
    def resolve_financial_summary(self, info, company_id, date, summary_type):
        try:
            # ✅ CORREGIDO: Usar zona horaria de Perú para filtros de fecha
            naive_date = datetime.strptime(date, '%Y-%m-%d').date()
            start_date = timezone.make_aware(
                datetime.combine(naive_date, datetime.min.time()),
                timezone=peru_tz
            )
            end_date = start_date + timedelta(days=1)

            # Solo pagos activos (is_enabled=True); los anulados no suman en totales
            base_query = Payment.objects.filter(
                company_id=company_id,
                payment_date__gte=start_date,
                payment_date__lt=end_date,
                is_enabled=True
            )

            if summary_type == 'income':
                result = base_query.filter(type='I').aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0
            elif summary_type == 'expense':
                result = base_query.filter(type='E').aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0
            elif summary_type == 'balance':
                income = base_query.filter(type='I').aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0
                expense = base_query.filter(type='E').aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0
                result = float(income) - float(expense)
            else:
                raise Exception("Tipo de resumen inválido")

            return float(result)
        except Exception as e:
            raise Exception(f"Error al calcular resumen: {str(e)}")

    # @staticmethod
    # def resolve_payment_monthly_report(self, info, company_id, year, month):
    #     # Obtener rango de fechas del mes
    #     start_date = datetime(year, month, 1).date()
    #     _, last_day = monthrange(year, month)
    #     end_date = datetime(year, month, last_day).date()
    #
    #     # Filtrar por empresa y rango de fechas
    #     operations = Operation.objects.filter(
    #         company_id=company_id,
    #         emit_date__range=[start_date, end_date]
    #     )
    #     start_datetime = datetime.combine(start_date, time.min)  # 00:00:00
    #     end_datetime = datetime.combine(end_date, time.max)  # 23:59:59.999999
    #     payments = Payment.objects.filter(
    #         company_id=company_id,
    #         payment_date__range=[start_datetime, end_datetime]
    #     )
    #
    #     # Calcular resumen general - CONVERTIR A FLOAT
    #     total_operations = float(operations.aggregate(
    #         total=Sum('total_amount')
    #     )['total'] or 0.0)
    #
    #     total_payments = float(payments.filter(type='I').aggregate(
    #         total=Sum('paid_amount')
    #     )['total'] or 0.0)
    #
    #     gross_profit = float(total_operations - total_payments)
    #
    #     # Operaciones por documento - CONVERTIR A FLOAT
    #     operations_by_document = []
    #     for doc in Document.objects.filter(company_id=company_id):
    #         doc_operations = operations.filter(document=doc)
    #         if doc_operations.exists():
    #             total_amount = float(doc_operations.aggregate(
    #                 total=Sum('total_amount')
    #             )['total'] or 0.0)
    #
    #             operations_by_document.append({
    #                 'document_id': doc.id,
    #                 'document_name': doc.description or doc.code,
    #                 'total_amount': total_amount,
    #                 'operation_count': doc_operations.count(),
    #                 'average_amount': float(total_amount / doc_operations.count())
    #             })
    #
    #     # Pagos por método - CONVERTIR A FLOAT
    #     payments_by_method = []
    #     payment_methods = {
    #         'E': 'EFECTIVO',
    #         'Y': 'YAPE',
    #         'P': 'PLIN',
    #         'T': 'TARJETA',
    #         'B': 'TRANSFERENCIA'
    #     }
    #
    #     for method_code, method_name in payment_methods.items():
    #         method_payments = payments.filter(
    #             payment_method=method_code,
    #             type='I'  # Solo ingresos
    #         )
    #
    #         if method_payments.exists():
    #             total_amount = float(method_payments.aggregate(
    #                 total=Sum('paid_amount')
    #             )['total'] or 0.0)
    #
    #             percentage = float((total_amount / total_payments * 100) if total_payments > 0 else 0)
    #
    #             payments_by_method.append({
    #                 'method': method_name,
    #                 'total_amount': total_amount,
    #                 'transaction_count': method_payments.count(),
    #                 'percentage': round(percentage, 2)
    #             })
    #
    #     # Datos diarios - CONVERTIR A FLOAT
    #     daily_data = []
    #     for day in range(1, last_day + 1):
    #         day_date = datetime(year, month, day).date()
    #
    #         day_operations = operations.filter(operation_date=day_date)
    #         day_payments = payments.filter(payment_date__date=day_date, type='I')
    #
    #         daily_data.append({
    #             'day': day,
    #             'operations_amount': float(day_operations.aggregate(
    #                 total=Sum('total_amount')
    #             )['total'] or 0.0),
    #             'payments_amount': float(day_payments.aggregate(
    #                 total=Sum('paid_amount')
    #             )['total'] or 0.0)
    #         })
    #
    #     return {
    #         'summary': {
    #             'total_operations': total_operations,
    #             'total_payments': total_payments,
    #             'gross_profit': gross_profit,
    #             'operation_count': operations.count(),
    #             'payment_count': payments.filter(type='I').count(),
    #             'average_daily_operations': float(total_operations / last_day),
    #             'average_daily_payments': float(total_payments / last_day)
    #         },
    #         'operations_by_document': operations_by_document,
    #         'payments_by_method': payments_by_method,
    #         'daily_data': daily_data
    #     }

    @staticmethod
    def resolve_payment_monthly_report(self, info, company_id, year, month):
        warnings.filterwarnings('ignore', category=RuntimeWarning, module='django.db.models.fields')
        # Obtener rango de fechas del mes
        start_date = datetime(year, month, 1).date()
        _, last_day = monthrange(year, month)
        end_date = datetime(year, month, last_day).date()

        # Filtrar por empresa y rango de fechas
        operations = Operation.objects.filter(
            company_id=company_id,
            emit_date__range=[start_date, end_date]
        )
        start_datetime = datetime.combine(start_date, time.min)  # 00:00:00
        end_datetime = datetime.combine(end_date, time.max)  # 23:59:59.999999
        # Pagos activos para totales; anulados (is_enabled=False) no se contabilizan
        payments = Payment.objects.filter(
            company_id=company_id,
            payment_date__range=[start_datetime, end_datetime],
            is_enabled=True
        )

        # SEPARAR OPERACIONES POR TIPO
        entrada_operations = operations.filter(operation_type='E')  # ENTRADA (Ventas)
        salida_operations = operations.filter(operation_type='S')  # SALIDA (Compras)

        # Calcular totales de operaciones
        total_entrada = float(entrada_operations.aggregate(
            total=Sum('total_amount')
        )['total'] or 0.0)

        total_salida = float(salida_operations.aggregate(
            total=Sum('total_amount')
        )['total'] or 0.0)

        # Ganancia bruta de operaciones (ventas - compras)
        gross_profit_operations = total_entrada - total_salida

        # SEPARAR PAGOS POR TIPO
        ingreso_payments = payments.filter(type='I')  # INGRESO
        egreso_payments = payments.filter(type='E')  # EGRESO

        # Calcular totales de pagos
        total_ingresos = float(ingreso_payments.aggregate(
            total=Sum('paid_amount')
        )['total'] or 0.0)

        total_egresos = float(egreso_payments.aggregate(
            total=Sum('paid_amount')
        )['total'] or 0.0)

        # Flujo de caja (ingresos - egresos)
        cash_flow = total_ingresos - total_egresos

        # Totales generales (para compatibilidad)
        total_operations = total_entrada + total_salida
        total_payments = total_ingresos + total_egresos
        gross_profit = gross_profit_operations  # Solo operaciones

        # Operaciones por documento (actualizado)
        operations_by_document = []
        for doc in Document.objects.filter(company_id=company_id):
            doc_entrada = entrada_operations.filter(document=doc)
            doc_salida = salida_operations.filter(document=doc)

            if doc_entrada.exists() or doc_salida.exists():
                entrada_amount = float(doc_entrada.aggregate(
                    total=Sum('total_amount')
                )['total'] or 0.0)

                salida_amount = float(doc_salida.aggregate(
                    total=Sum('total_amount')
                )['total'] or 0.0)

                net_amount = entrada_amount - salida_amount
                total_count = doc_entrada.count() + doc_salida.count()

                operations_by_document.append({
                    'document_id': doc.id,
                    'document_name': doc.description or doc.code,
                    'total_amount': net_amount,  # Monto neto (entrada - salida)
                    'operation_count': total_count,
                    'average_amount': net_amount / total_count if total_count > 0 else 0.0
                })

        # Pagos por método (SEPARADOS POR INGRESO/EGRESO)
        payments_by_method = []
        payment_methods = {
            'E': 'EFECTIVO',
            'Y': 'YAPE',
            'P': 'PLIN',
            'T': 'TARJETA',
            'B': 'TRANSFERENCIA'
        }

        # INGRESOS por método
        for method_code, method_name in payment_methods.items():
            ingreso_method_payments = ingreso_payments.filter(payment_method=method_code)

            if ingreso_method_payments.exists():
                total_ingreso = float(ingreso_method_payments.aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0.0)

                payments_by_method.append({
                    'method': f"{method_name} (INGRESO)",
                    'total_amount': total_ingreso,
                    'transaction_count': ingreso_method_payments.count(),
                    'percentage': float((total_ingreso / total_ingresos * 100) if total_ingresos > 0 else 0),
                    'type': 'INGRESO',
                    'method_code': method_code
                })

        # EGRESOS por método
        for method_code, method_name in payment_methods.items():
            egreso_method_payments = egreso_payments.filter(payment_method=method_code)

            if egreso_method_payments.exists():
                total_egreso = float(egreso_method_payments.aggregate(
                    total=Sum('paid_amount')
                )['total'] or 0.0)

                payments_by_method.append({
                    'method': f"{method_name} (EGRESO)",
                    'total_amount': total_egreso,
                    'transaction_count': egreso_method_payments.count(),
                    'percentage': float((total_egreso / total_egresos * 100) if total_egresos > 0 else 0),
                    'type': 'EGRESO',
                    'method_code': method_code
                })

        # Datos diarios (actualizado)
        daily_data = []
        for day in range(1, last_day + 1):
            day_date = datetime(year, month, day).date()

            # Operaciones del día
            day_entrada = entrada_operations.filter(emit_date=day_date)
            day_salida = salida_operations.filter(emit_date=day_date)

            entrada_amount = float(day_entrada.aggregate(
                total=Sum('total_amount')
            )['total'] or 0.0)

            salida_amount = float(day_salida.aggregate(
                total=Sum('total_amount')
            )['total'] or 0.0)

            operations_amount = entrada_amount - salida_amount  # Neto del día
            # Crear rango de fechas para el día (00:00:00 a 23:59:59.999999)
            day_start = datetime.combine(day_date, time.min)  # 00:00:00
            day_end = datetime.combine(day_date, time.max)  # 23:59:59.999999
            # Pagos del día
            day_ingresos = ingreso_payments.filter(payment_date__range=[day_start, day_end])
            day_egresos = egreso_payments.filter(payment_date__range=[day_start, day_end])

            ingresos_amount = float(day_ingresos.aggregate(
                total=Sum('paid_amount')
            )['total'] or 0.0)

            egresos_amount = float(day_egresos.aggregate(
                total=Sum('paid_amount')
            )['total'] or 0.0)

            payments_amount = ingresos_amount - egresos_amount  # Neto del día

            daily_data.append({
                'day': day,
                'entrada_amount': entrada_amount,
                'salida_amount': salida_amount,
                'operations_amount': operations_amount,  # Neto
                'ingresos_amount': ingresos_amount,
                'egresos_amount': egresos_amount,
                'payments_amount': payments_amount  # Neto
            })

        return {
            'summary': {
                # Operaciones
                'total_entrada': total_entrada,
                'total_salida': total_salida,
                'gross_profit_operations': gross_profit_operations,

                # Pagos
                'total_ingresos': total_ingresos,
                'total_egresos': total_egresos,
                'cash_flow': cash_flow,

                # Totales generales
                'total_operations': total_operations,
                'total_payments': total_payments,
                'gross_profit': gross_profit,

                # Contadores
                'operation_count': operations.count(),
                'payment_count': payments.count(),

                # Promedios
                'average_daily_operations': total_operations / last_day,
                'average_daily_payments': total_payments / last_day
            },
            'operations_by_document': operations_by_document,
            'payments_by_method': payments_by_method,
            'daily_data': daily_data
        }

class FinancesMutation(graphene.ObjectType):
    create_payment = CreatePayment.Field()
    update_payment = UpdatePayment.Field()
    delete_payment = DeletePayment.Field()
    cancel_payment = CancelPayment.Field()
