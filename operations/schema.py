import re
import graphene
from django.db import transaction
import logging

from django.db.models.functions import Extract

from finances.models import Payment
from operations import models
from operations.apis import ApisNetPe
from operations.models import Person
from operations.mutations import PersonMutation, CreateOperation, CancelOperation, CreatePerson
from operations.types import *
from django.conf import settings
from datetime import datetime, timedelta, date
from django.db.models import Sum, Value, Count, Q, F, Avg, When, Case, IntegerField
from django.utils import timezone
import requests
import graphene
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Avg, F, Q, Max
from django.db.models.functions import TruncDate
import calendar
import pytz

# Configurar logger
logger = logging.getLogger(__name__)


class OperationsQuery(graphene.ObjectType):
    # Documentos
    documents = graphene.List(DocumentType, company_id=graphene.ID(required=True))
    serials_by_document = graphene.List(
        SerialType,
        document_id=graphene.ID(required=True)
    )

    # Salidas y Entradas
    operations_by_date = graphene.List(
        OperationType,
        company_id=graphene.ID(required=True),
        date=graphene.String(required=True),
        operation_type=graphene.String(required=True)
    )
    operation_by_id = graphene.Field(
        OperationType,
        operation_id=graphene.ID(required=True)
    )
    operations_by_date_range = graphene.List(
        OperationType,
        company_id=graphene.ID(required=True),
        start_date=graphene.String(required=True),
        end_date=graphene.String(required=True),
        operation_type=graphene.String()
    )
    pending_operations = graphene.List(
        OperationType,
        company_id=graphene.ID(required=True)
    )

    # Resumen de ventas
    sales_summary = graphene.Field(
        'operations.schema.SalesSummaryType',
        company_id=graphene.ID(required=True),
        start_date=graphene.String(required=True),
        end_date=graphene.String(required=True)
    )

    # Personas
    search_person = graphene.List(
        PersonType,
        document=graphene.String(required=True)
    )
    # Búsqueda avanzada de personas
    search_persons_advanced = graphene.List(
        PersonType,
        search=graphene.String(required=True),
        limit=graphene.Int(default_value=20)
    )

    monthly_report = graphene.Field(
        MonthlyReportType,
        company_id=graphene.ID(required=True),
        start_date=graphene.String(required=True),
        end_date=graphene.String(required=True)
    )
    monthly_summary = graphene.Field(
        MonthlyReportType,
        company_id=graphene.ID(required=True),
        year=graphene.Int(required=True),
        month=graphene.Int(required=True)
    )
    # Reporte diario completo
    daily_report = graphene.Field(
        DailyReportType,
        company_id=graphene.Int(required=True),
        date=graphene.String(required=False)
    )

    # Resumen diario rápido
    daily_summary = graphene.Field(
        DailySummaryType,
        company_id=graphene.Int(required=True),
        date=graphene.String(required=False)
    )

    monthly_reports = graphene.Field(
        MonthlyReportsType,
        company_id=graphene.ID(required=True),
        year=graphene.Int(required=True),
        month=graphene.Int(required=True)
    )

    @staticmethod
    def resolve_documents(root, info, company_id):
        return Document.objects.filter(company_id=company_id).order_by('code')

    @staticmethod
    def resolve_serials_by_document(root, info, document_id):
        return Serial.objects.filter(document_id=document_id).order_by('serial')

    @staticmethod
    def resolve_operations_by_date(root, info, company_id, date, operation_type):
        emit_date = datetime.strptime(date, '%Y-%m-%d').date()
        return Operation.objects.filter(
            company_id=company_id,
            emit_date=emit_date,
            operation_type=operation_type
        ).select_related(
            'document', 'person', 'user'
        ).order_by('-created_at')

    @staticmethod
    def resolve_operation_by_id(root, info, operation_id):
        try:
            return Operation.objects.select_related(
                'document', 'person', 'user', 'company'
            ).prefetch_related(
                'operationdetail_set__product__unit',
                'operationdetail_set__product__type_affectation',
                'operationdetail_set__type_affectation'
            ).get(id=operation_id)
        except Operation.DoesNotExist:
            return None

    @staticmethod
    def resolve_search_person(self, info, document: str):
        """
        Busca una persona por documento (DNI o RUC).
        1. Primero busca en base de datos local
        2. Si no encuentra, consulta API externa
        3. Guarda en BD y retorna el resultado
        """
        try:
            # Limpiar y validar formato del documento
            document = document.strip()
            if not document:
                logger.warning("Documento vacío")
                return []

            # Validar que sea numérico
            if not document.isdigit():
                logger.warning(f"Documento inválido (no numérico): {document}")
                return []

            # 1. Buscar en base de datos local
            logger.info(f"Buscando documento {document} en base de datos local...")

            try:
                existing_persons = Person.objects.filter(document=document)

                if existing_persons.exists():
                    logger.info(f"Persona encontrada en BD local: {document}")
                    return list(existing_persons)

            except Exception as e:
                logger.error(f"Error al buscar en BD local: {str(e)}")
                # Continuar con la búsqueda en API externa

            # 2. Si no existe, consultar API externa
            logger.info(f"Documento {document} no encontrado en BD. Consultando API externa...")

            document_length = len(document)

            # Validar longitud del documento
            if document_length not in [8, 11]:
                logger.warning(f"Documento con longitud inválida: {document_length} caracteres")
                return []

            # Determinar tipo de persona según longitud
            person_type = "1" if document_length == 8 else "6"  # 1=DNI, 6=RUC

            # Obtener token de la configuración
            api_token = getattr(settings, 'APIS_NET_PE_TOKEN', None)
            if not api_token:
                logger.error("Token de API no configurado en settings.APIS_NET_PE_TOKEN")
                return []

            # Importar y crear instancia de la API
            try:
                api_client = ApisNetPe(token=api_token)
            except ImportError as e:
                logger.error(f"Error al importar ApisNetPe: {str(e)}")
                return []

            # Consultar según tipo de documento
            api_data = None
            try:
                if document_length == 8:
                    logger.info("Consultando DNI en API externa...")
                    api_data = api_client.get_person(document)
                else:
                    logger.info("Consultando RUC en API externa...")
                    api_data = api_client.get_company(document)

            except requests.exceptions.Timeout:
                logger.error("Timeout al consultar API externa")
                return []
            except requests.exceptions.ConnectionError:
                logger.error("Error de conexión con API externa")
                return []
            except requests.exceptions.RequestException as e:
                logger.error(f"Error de requests al consultar API: {str(e)}")
                return []
            except Exception as e:
                logger.error(f"Error inesperado al consultar API: {str(e)}")
                return []

            # Verificar respuesta de la API
            if not api_data:
                logger.warning(f"API no retornó datos para documento: {document}")
                return []

            if not api_data.get('success', False):
                logger.warning(f"API retornó success=False para documento: {document}")
                return []

            # 3. Crear nueva persona con los datos de la API
            try:
                with transaction.atomic():
                    # Preparar datos según tipo de persona
                    person_data = {
                        'document': document,
                        'person_type': person_type,
                        'is_customer': True,  # Por defecto lo marcamos como cliente
                        'is_supplier': False
                    }

                    if document_length == 8:  # Persona Natural (DNI)
                        # Construir nombre completo
                        nombres = api_data.get('nombres', '').strip()
                        apellido_paterno = api_data.get('paterno', '').strip()
                        apellido_materno = api_data.get('materno', '').strip()

                        # Formato: APELLIDO_PATERNO APELLIDO_MATERNO, NOMBRES
                        if apellido_paterno or apellido_materno or nombres:
                            full_name_parts = []
                            if apellido_paterno:
                                full_name_parts.append(apellido_paterno)
                            if apellido_materno:
                                full_name_parts.append(apellido_materno)

                            full_name = ' '.join(full_name_parts)
                            if nombres:
                                full_name = f"{full_name}, {nombres}" if full_name else nombres
                        else:
                            full_name = f"PERSONA DNI {document}"

                        person_data.update({
                            'full_name': full_name,
                            'address': api_data.get('direccion', '-')
                        })

                    else:  # Persona Jurídica (RUC)
                        razon_social = api_data.get('razon_social', '').strip()
                        if not razon_social:
                            razon_social = f"EMPRESA RUC {document}"

                        person_data.update({
                            'full_name': razon_social,
                            'address': api_data.get('direccion_completa', '') or api_data.get('direccion', '')
                        })

                    # Crear la persona
                    new_person = Person.objects.create(**person_data)

                    logger.info(f"Persona creada exitosamente: {document} - {new_person.full_name}")

                    # Retornar la nueva persona como lista
                    return [new_person]

            except Exception as e:
                logger.error(f"Error al guardar persona en BD: {str(e)}")

                # Si hay error al guardar, crear objeto temporal para retornar
                try:
                    # Crear objeto Person temporal (no guardado en BD)
                    temp_person = Person()
                    temp_person.id = None  # Indicar que no está guardado
                    temp_person.document = document
                    temp_person.person_type = person_type
                    temp_person.is_customer = True
                    temp_person.is_supplier = False

                    if document_length == 8:
                        nombres = api_data.get('nombres', '')
                        paterno = api_data.get('paterno', '')
                        materno = api_data.get('materno', '')

                        full_name = f"{paterno} {materno}".strip()
                        if nombres:
                            full_name = f"{full_name}, {nombres}".strip(", ")

                        temp_person.full_name = full_name or f"PERSONA DNI {document}"
                        temp_person.address = api_data.get('direccion', '')
                    else:
                        temp_person.full_name = api_data.get('razon_social', '') or f"EMPRESA RUC {document}"
                        temp_person.address = api_data.get('direccion_completa', '') or api_data.get('direccion', '')

                    temp_person.phone = ''
                    temp_person.email = ''

                    # Marcar como temporal
                    temp_person._is_temporary = True

                    logger.info(f"Retornando persona temporal: {temp_person.full_name}")
                    return [temp_person]

                except Exception as temp_error:
                    logger.error(f"Error al crear objeto temporal: {str(temp_error)}")
                    return []

        except Exception as e:
            logger.error(f"Error general en search_person: {str(e)}", exc_info=True)
            return []

    def resolve_search_persons_advanced(self, info, search, limit=20):
        """
        Búsqueda avanzada de personas con tolerancia a errores
        """
        search = search.strip().lower()
        if not search or len(search) < 2:
            return []

        # Limpiar caracteres especiales pero mantener espacios
        search_clean = re.sub(r'[^\w\s]', '', search)
        words = search_clean.split()

        if not words:
            return []

        # ESTRATEGIA 1: Búsqueda exacta por documento
        exact_doc_query = Q(document__iexact=search)

        # ESTRATEGIA 2: Documento contiene la búsqueda
        doc_contains_query = Q(document__icontains=search)

        # ESTRATEGIA 3: Nombre exacto
        name_exact_query = Q(full_name__iexact=search)

        # ESTRATEGIA 4: Contiene la frase completa en el nombre
        name_phrase_query = Q(full_name__icontains=search)

        # ESTRATEGIA 5: Todas las palabras en el nombre (AND)
        all_words_query = Q()
        for word in words:
            all_words_query &= Q(full_name__icontains=word)

        # ESTRATEGIA 6: Al menos una palabra (OR)
        any_word_query = Q()
        for word in words:
            if len(word) >= 2:
                any_word_query |= Q(full_name__icontains=word)

        # ESTRATEGIA 7: Empieza con la primera palabra
        prefix_query = Q()
        if words:
            first_word = words[0]
            if len(first_word) >= 2:
                prefix_query = Q(full_name__istartswith=first_word)

        # Obtener personas base
        base_queryset = Person.objects.all()

        # Ejecutar búsqueda con scoring
        persons = base_queryset.annotate(
            relevance_score=Case(
                # Documento exacto = 100 puntos
                When(exact_doc_query, then=Value(100)),
                # Documento contiene = 90 puntos
                When(doc_contains_query, then=Value(90)),
                # Nombre exacto = 85 puntos
                When(name_exact_query, then=Value(85)),
                # Contiene frase completa en nombre = 80 puntos
                When(name_phrase_query, then=Value(80)),
                # Todas las palabras = 70 puntos
                When(all_words_query, then=Value(70)),
                # Empieza con primera palabra = 60 puntos
                When(prefix_query, then=Value(60)),
                # Al menos una palabra = 50 puntos
                When(any_word_query, then=Value(50)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).filter(
            relevance_score__gt=0
        ).order_by('-relevance_score', 'full_name')[:limit * 2]

        # Si ya tenemos buenos resultados, retornarlos
        if len(persons) <= limit:
            return persons

        # Similitud adicional para refinar resultados
        scored_persons = []
        for person in persons:
            name_lower = person.full_name.lower() if person.full_name else ""
            doc_lower = person.document.lower() if person.document else ""

            # Calcular similitud
            name_similarity = self._quick_similarity(search, name_lower)
            doc_similarity = self._quick_similarity(search, doc_lower)

            # Bonus si contiene todas las palabras en orden
            order_bonus = 10 if all(word in name_lower for word in words) else 0

            # Score final
            final_score = person.relevance_score + (max(name_similarity, doc_similarity) * 20) + order_bonus

            scored_persons.append({
                'person': person,
                'score': final_score
            })

        # Ordenar y retornar los mejores
        scored_persons.sort(key=lambda x: x['score'], reverse=True)
        return [item['person'] for item in scored_persons[:limit]]

    def _quick_similarity(self, search, text):
        """Cálculo rápido de similitud"""
        if not text:
            return 0
        if search in text:
            return 1.0

        common = sum(1 for char in search if char in text)
        return common / len(search) if search else 0

    @staticmethod
    def resolve_sales_summary(root, info, company_id, start_date, end_date):
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        operations = Operation.objects.filter(
            company_id=company_id,
            emit_date__range=[start, end],
            operation_type='S',
            operation_status__in=['1', '2']
        )

        summary = operations.aggregate(
            total_sales=Count('id'),
            total_amount=Sum('total_amount') or 0,
            total_igv=Sum('igv_amount') or 0,
            total_discount=Sum('total_discount') or 0
        )

        avg_ticket = summary['total_amount'] / summary['total_sales'] if summary['total_sales'] > 0 else 0

        # Top productos
        top_products = OperationDetail.objects.filter(
            operation__in=operations
        ).values(
            'product_id', 'product__description'
        ).annotate(
            quantity=Sum('quantity'),
            total_amount=Sum('total_amount')
        ).order_by('-total_amount')[:10]

        return SalesSummaryType(
            total_sales=summary['total_sales'],
            total_amount=float(summary['total_amount']),
            total_igv=float(summary['total_igv']),
            total_discount=float(summary['total_discount']),
            average_ticket=float(avg_ticket),
            top_products=[
                TopProductType(
                    product_id=p['product_id'],
                    product_name=p['product__description'],
                    quantity=float(p['quantity']),
                    total_amount=float(p['total_amount'])
                ) for p in top_products
            ]
        )

    @staticmethod
    def resolve_operations_by_date_range(root, info, company_id, start_date, end_date, operation_type=None):
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        queryset = Operation.objects.filter(
            company_id=company_id,
            emit_date__range=[start, end]
        ).select_related('document', 'person', 'user')

        if operation_type:
            queryset = queryset.filter(operation_type=operation_type)

        return queryset.order_by('-emit_date', '-created_at')

    @staticmethod
    def resolve_pending_operations(root, info, company_id):
        from datetime import timedelta
        from django.utils import timezone

        return Operation.objects.filter(
            company_id=company_id,
            operation_status__in=['3', '4']  # Pendiente de baja o En proceso de baja
        ).select_related('document', 'person').annotate(
            days_since_pending=timezone.now() - models.F('low_date')
        )

    @staticmethod
    def resolve_monthly_report(self, info, company_id, start_date, end_date):
        # Convertir strings a fechas
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        # Filtro base para operaciones válidas
        base_filter = Q(
            company_id=company_id,
            emit_date__gte=start,
            emit_date__lte=end
        ) & ~Q(operation_status__in=['5', '6'])  # Excluir anuladas y rechazadas

        # 1. Obtener operaciones diarias agrupadas
        daily_operations = []

        # Agrupar por día
        daily_data = Operation.objects.filter(base_filter).values(
            'emit_date'
        ).annotate(
            day=Extract('emit_date', 'day'),
            # Ventas (operationType = 'S')
            total_sales=Sum(
                'total_amount',
                filter=Q(operation_type='S')
            ),
            sales_count=Count(
                'id',
                filter=Q(operation_type='S')
            ),
            # Compras (operationType = 'E')
            total_purchases=Sum(
                'total_amount',
                filter=Q(operation_type='E')
            ),
            purchases_count=Count(
                'id',
                filter=Q(operation_type='E')
            )
        ).order_by('emit_date')

        # Convertir a formato esperado
        for day_data in daily_data:
            daily_operations.append(DailyOperationType(
                day=day_data['day'],
                date=day_data['emit_date'].strftime('%Y-%m-%d'),
                total_sales=float(day_data['total_sales'] or 0),
                total_purchases=float(day_data['total_purchases'] or 0),
                sales_count=day_data['sales_count'] or 0,
                purchases_count=day_data['purchases_count'] or 0
            ))

        # 2. Obtener top productos
        top_products = []

        # Top productos vendidos (ventas)
        top_sales = OperationDetail.objects.filter(
            operation__company_id=company_id,
            operation__emit_date__gte=start,
            operation__emit_date__lte=end,
            operation__operation_type='S'
        ).exclude(
            operation__operation_status__in=['5', '6']
        ).values(
            'product_id',
            'product__description',
            'product__code'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_amount=Sum('total_amount')
        ).order_by('-total_amount')[:10]

        for product in top_sales:
            # Calcular precio promedio después de la agregación
            avg_price = float(product['total_amount'] / product['total_quantity']) if product[
                                                                                          'total_quantity'] > 0 else 0

            top_products.append(TopProductType(
                product_id=product['product_id'],
                product_name=product['product__description'],
                product_code=product['product__code'],
                quantity=float(product['total_quantity']),
                total_amount=float(product['total_amount']),
                operation_type='S',
                average_price=avg_price
            ))

        # Top productos comprados
        top_purchases = OperationDetail.objects.filter(
            operation__company_id=company_id,
            operation__emit_date__gte=start,
            operation__emit_date__lte=end,
            operation__operation_type='E'
        ).exclude(
            operation__operation_status__in=['5', '6']
        ).values(
            'product_id',
            'product__description',
            'product__code'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_amount=Sum('total_amount')
        ).order_by('-total_amount')[:10]

        for product in top_purchases:
            # Calcular precio promedio después de la agregación
            avg_price = float(product['total_amount'] / product['total_quantity']) if product[
                                                                                          'total_quantity'] > 0 else 0

            top_products.append(TopProductType(
                product_id=product['product_id'],
                product_name=product['product__description'],
                product_code=product['product__code'],
                quantity=float(product['total_quantity']),
                total_amount=float(product['total_amount']),
                operation_type='E',
                average_price=avg_price
            ))

        # 3. Calcular totales generales
        totals = Operation.objects.filter(base_filter).aggregate(
            total_sales=Sum(
                'total_amount',
                filter=Q(operation_type='S')
            ),
            total_purchases=Sum(
                'total_amount',
                filter=Q(operation_type='E')
            ),
            total_transactions=Count('id')
        )

        total_sales = float(totals['total_sales'] or 0)
        total_purchases = float(totals['total_purchases'] or 0)
        total_profit = total_sales - total_purchases

        return MonthlyReportType(
            daily_operations=daily_operations,
            top_products=top_products,
            total_transactions=totals['total_transactions'] or 0,
            total_sales=total_sales,
            total_purchases=total_purchases,
            total_profit=total_profit
        )

    def resolve_monthly_summary(self, info, company_id, year, month):
        from calendar import monthrange

        # Calcular primer y último día del mes
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

        # Usar la misma lógica que monthly_report
        return self.resolve_monthly_report(
            info,
            company_id,
            first_day.strftime('%Y-%m-%d'),
            last_day.strftime('%Y-%m-%d')
        )

    @staticmethod
    def resolve_daily_report(root, info, company_id, date=None):
        # Si no se especifica fecha, usar hoy
        if not date:
            target_date = timezone.now().date()
        else:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()

        # Fecha del día anterior para comparación
        previous_date = target_date - timedelta(days=1)

        # Filtro base para el día actual
        base_filter = Q(
            company_id=company_id,
            emit_date=target_date
        ) & ~Q(operation_status__in=['5', '6'])  # Excluir anuladas y rechazadas

        # 1. Obtener totales del día
        daily_totals = Operation.objects.filter(base_filter).aggregate(
            total_sales=Sum(
                'total_amount',
                filter=Q(operation_type='S')
            ),
            sales_count=Count(
                'id',
                filter=Q(operation_type='S')
            ),
            total_purchases=Sum(
                'total_amount',
                filter=Q(operation_type='E')
            ),
            purchases_count=Count(
                'id',
                filter=Q(operation_type='E')
            )
        )

        # 2. Calcular crecimiento comparado con el día anterior
        previous_sales = Operation.objects.filter(
            company_id=company_id,
            emit_date=previous_date,
            operation_type='S'
        ).exclude(
            operation_status__in=['5', '6']
        ).aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        current_sales = daily_totals['total_sales'] or 0
        sales_growth = 0
        if previous_sales > 0:
            sales_growth = ((current_sales - previous_sales) / previous_sales) * 100

        # 3. Obtener últimos productos vendidos (últimas 10 operaciones del día)
        last_operations = Operation.objects.filter(
            base_filter,
            operation_type='S'
        ).order_by('-emit_time', '-id')[:10]

        last_sold_products = []
        for operation in last_operations:
            details = OperationDetail.objects.filter(
                operation=operation
            ).select_related('product', 'product__unit')[:3]  # Máximo 3 productos por operación

            for detail in details:
                if detail.product:  # Verificar que el producto existe
                    last_sold_products.append(SoldProductType(
                        product_id=detail.product.id,
                        product_name=detail.product.description or '',
                        product_code=detail.product.code or '',
                        quantity=float(detail.quantity or 0),
                        unit=detail.product.unit.description if detail.product.unit else 'UND',
                        unit_price=float(detail.unit_price or 0),
                        total=float(detail.total_amount or 0),
                        timestamp=operation.emit_time.isoformat() if operation.emit_time else '',
                        operation_id=operation.id
                    ))

        # Limitar a los últimos 15 productos
        last_sold_products = last_sold_products[:15]

        # 4. Ventas por hora del día (usando SQL raw para EXTRACT)
        from django.db import connection

        hourly_sales = []
        with connection.cursor() as cursor:
            cursor.execute("""
                    SELECT 
                        EXTRACT(hour FROM emit_time) as hour,
                        SUM(total_amount) as sales_amount,
                        COUNT(*) as sales_count
                    FROM operations_operation
                    WHERE company_id = %s 
                        AND emit_date = %s 
                        AND operation_type = 'S'
                        AND operation_status NOT IN ('5', '6')
                        AND emit_time IS NOT NULL
                    GROUP BY EXTRACT(hour FROM emit_time)
                    ORDER BY hour
                """, [company_id, target_date])

            for row in cursor.fetchall():
                hourly_sales.append(HourlySalesType(
                    hour=int(row[0]),
                    sales_amount=float(row[1] or 0),
                    sales_count=row[2] or 0
                ))

        # 5. Hora con más ventas
        top_selling_hour = ''
        if hourly_sales:
            top_hour = max(hourly_sales, key=lambda x: x.sales_amount)
            top_selling_hour = f"{top_hour.hour:02d}:00"

        return DailyReportType(
            total_sales=float(daily_totals['total_sales'] or 0),
            total_purchases=float(daily_totals['total_purchases'] or 0),
            sales_count=daily_totals['sales_count'] or 0,
            purchases_count=daily_totals['purchases_count'] or 0,
            sales_growth=float(sales_growth),
            last_sold_products=last_sold_products,
            hourly_sales=hourly_sales,
            top_selling_hour=top_selling_hour
        )

    @staticmethod
    def resolve_daily_summary(root, info, company_id, date=None):
        # Resumen rápido sin detalles
        if not date:
            target_date = timezone.now().date()
        else:
            target_date = datetime.strptime(date, '%Y-%m-%d').date()

        # Una sola consulta optimizada
        summary = Operation.objects.filter(
            company_id=company_id,
            emit_date=target_date
        ).exclude(
            operation_status__in=['5', '6']
        ).aggregate(
            total_sales=Sum(
                'total_amount',
                filter=Q(operation_type='S')
            ),
            sales_count=Count(
                'id',
                filter=Q(operation_type='S')
            ),
            total_purchases=Sum(
                'total_amount',
                filter=Q(operation_type='E')
            ),
            purchases_count=Count(
                'id',
                filter=Q(operation_type='E')
            ),
            average_ticket=Avg(
                'total_amount',
                filter=Q(operation_type='S')
            )
        )

        total_sales = float(summary['total_sales'] or 0)
        total_purchases = float(summary['total_purchases'] or 0)

        return DailySummaryType(
            total_sales=total_sales,
            total_purchases=total_purchases,
            sales_count=summary['sales_count'] or 0,
            purchases_count=summary['purchases_count'] or 0,
            balance=total_sales - total_purchases,
            average_ticket=float(summary['average_ticket'] or 0)
        )

    @staticmethod
    def resolve_monthly_reports(self, info, company_id, year, month):
        # Configurar la zona horaria de Perú
        lima_tz = pytz.timezone('America/Lima')
        # Calcular primer y último día del mes en la zona horaria de Lima
        first_day = lima_tz.localize(datetime(year, month, 1))
        last_day = lima_tz.localize(datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59))
        # Calcular primer y último día del mes
        # first_day = datetime(year, month, 1)
        # last_day = datetime(year, month, calendar.monthrange(year, month)[1])

        # Filtrar operaciones del mes que NO estén anuladas
        operations = Operation.objects.filter(
            company_id=company_id,
            emit_date__gte=first_day,
            emit_date__lte=last_day
        ).exclude(
            operation_status__in=['3', '4', '5', '6']  # Excluir anuladas
        )

        # 1. DAILY REPORTS
        # Método alternativo sin TruncDate y con manejo de zona horaria
        from django.utils import timezone

        daily_dict = {}
        for operation in operations:
            if operation.emit_date is None:
                continue
            # Convertir la fecha a la zona horaria de Lima
            # lima_date = timezone.localtime(operation.emit_date, timezone=lima_tz).date()
            date_str = operation.emit_date.strftime('%Y-%m-%d')
            # Si emit_date es DateTimeField, convertir a la zona horaria local
            # Si es DateField, usar directamente
            # if hasattr(operation.emit_date, 'astimezone'):
            #     # Es DateTimeField - convertir a zona horaria local
            #     local_date = timezone.localtime(operation.emit_date).date()
            #     date_str = local_date.strftime('%Y-%m-%d')
            # else:
            #     # Es DateField - usar directamente
            #     date_str = operation.emit_date.strftime('%Y-%m-%d')

            if date_str not in daily_dict:
                daily_dict[date_str] = {
                    'date': date_str,
                    'entries': 0,
                    'entries_amount': 0,
                    'sales': 0,
                    'sales_amount': 0,
                    'profit': 0,
                    'transaction_count': 0
                }

            if operation.operation_type == 'E':  # Entrada
                daily_dict[date_str]['entries'] += 1
                daily_dict[date_str]['entries_amount'] += float(operation.total_amount or 0)
            else:  # Salida
                daily_dict[date_str]['sales'] += 1
                daily_dict[date_str]['sales_amount'] += float(operation.total_amount or 0)

            daily_dict[date_str]['transaction_count'] += 1
            daily_dict[date_str]['profit'] = (
                    daily_dict[date_str]['sales_amount'] -
                    daily_dict[date_str]['entries_amount']
            )

        # Ordenar por fecha
        daily_reports = sorted(list(daily_dict.values()), key=lambda x: x['date'])

        # 2. PRODUCT REPORTS
        # Obtener detalles de operaciones
        details = OperationDetail.objects.filter(
            operation__in=operations
        ).values(
            'product_id',
            'product__description',
            'product__code',
            'operation__operation_type'
        ).annotate(
            quantity=Sum('quantity'),
            total=Sum('total_amount')
        )

        # Organizar por producto
        product_dict = {}
        for detail in details:
            product_id = detail['product_id']
            if product_id not in product_dict:
                product_dict[product_id] = {
                    'product_id': str(product_id),  # Convertir a string
                    'product_name': detail['product__description'] or 'Sin nombre',
                    'product_code': detail['product__code'] or 'Sin código',
                    'quantity_sold': 0,
                    'quantity_purchased': 0,
                    'total_sales': 0,
                    'total_purchases': 0,
                    'profit': 0,
                    'stock_movement': 0
                }

            if detail['operation__operation_type'] == 'E':  # Entrada
                product_dict[product_id]['quantity_purchased'] = float(detail['quantity'] or 0)
                product_dict[product_id]['total_purchases'] = float(detail['total'] or 0)
            else:  # Salida
                product_dict[product_id]['quantity_sold'] = float(detail['quantity'] or 0)
                product_dict[product_id]['total_sales'] = float(detail['total'] or 0)

            product_dict[product_id]['profit'] = (
                    product_dict[product_id]['total_sales'] -
                    product_dict[product_id]['total_purchases']
            )
            product_dict[product_id]['stock_movement'] = (
                    product_dict[product_id]['quantity_purchased'] -
                    product_dict[product_id]['quantity_sold']
            )

        product_reports = list(product_dict.values())

        # 3. STATS
        total_sales = operations.filter(operation_type='S').aggregate(
            count=Count('id'),
            total=Sum('total_amount')
        )
        total_entries = operations.filter(operation_type='E').aggregate(
            count=Count('id'),
            total=Sum('total_amount')
        )

        days_in_month = calendar.monthrange(year, month)[1]
        total_sales_amount = float(total_sales['total'] or 0)
        total_entries_amount = float(total_entries['total'] or 0)

        # Calcular growth rate (comparar con mes anterior)
        if month == 1:
            prev_month = 12
            prev_year = year - 1
        else:
            prev_month = month - 1
            prev_year = year

        prev_first_day = datetime(prev_year, prev_month, 1)
        prev_last_day = datetime(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])

        prev_sales = Operation.objects.filter(
            company_id=company_id,
            operation_type='S',
            emit_date__gte=prev_first_day,  # CAMBIADO A emit_date
            emit_date__lte=prev_last_day  # CAMBIADO A emit_date
        ).exclude(
            operation_status__in=['3', '4', '5', '6']  # Usar mismos estados excluidos
        ).aggregate(total=Sum('total_amount'))

        prev_total = float(prev_sales['total'] or 0)
        growth_rate = 0
        if prev_total > 0:
            growth_rate = ((total_sales_amount - prev_total) / prev_total) * 100

        stats = {
            'total_entries': total_entries['count'] or 0,
            'total_entries_amount': total_entries_amount,
            'total_sales': total_sales['count'] or 0,
            'total_sales_amount': total_sales_amount,
            'total_profit': total_sales_amount - total_entries_amount,
            'avg_daily_sales': total_sales_amount / days_in_month if days_in_month > 0 else 0,
            'avg_daily_entries': total_entries_amount / days_in_month if days_in_month > 0 else 0,
            'growth_rate': growth_rate
        }

        # 4. PAYMENT METHODS
        payment_methods = []
        try:
            # Filtrar pagos de las operaciones de venta (S) del mes
            payments = Payment.objects.filter(
                operation__in=operations.filter(operation_type='S'),
                status='C',  # Solo pagos cancelados (completados)
                type='I',  # Solo ingresos (pagos recibidos)
                is_enabled=True  # Solo pagos habilitados
            ).values('payment_method').annotate(
                count=Count('id'),
                total=Sum('paid_amount')
            ).order_by('-total')  # Ordenar por monto descendente

            total_payments = sum(float(p['total'] or 0) for p in payments)

            # Mapeo de métodos de pago según tu modelo
            method_names = {
                'E': 'Efectivo',
                'Y': 'Yape',
                'P': 'Plin',
                'T': 'Tarjeta',
                'B': 'Transferencia'
            }

            for payment in payments:
                amount = float(payment['total'] or 0)
                percentage = (amount / total_payments * 100) if total_payments > 0 else 0

                payment_methods.append({
                    'method': payment['payment_method'],
                    'method_name': method_names.get(
                        payment['payment_method'],
                        payment['payment_method']  # Valor por defecto si no está en el mapeo
                    ),
                    'count': payment['count'],
                    'amount': amount,
                    'percentage': round(percentage, 2)  # Redondear a 2 decimales
                })

            # Ordenar por cantidad (opcional)
            payment_methods.sort(key=lambda x: x['amount'], reverse=True)

        except Exception as e:
            print(f"Error obteniendo métodos de pago: {str(e)}")
            payment_methods = []  # Retornar lista vacía en caso de error

        # 5. TOP CUSTOMERS
        top_customers = []
        try:
            customers = operations.filter(
                operation_type='S'
            ).exclude(
                person__isnull=True
            ).values(
                'person_id',
                'person__full_name',
                'person__document'
            ).annotate(
                count=Count('id'),
                total=Sum('total_amount'),
                avg=Avg('total_amount'),
                last_date=Max('emit_date')  # CAMBIADO A emit_date
            ).order_by('-total')[:10]

            for customer in customers:
                # Manejar correctamente las fechas nulas y otros campos
                last_purchase_date = None
                if customer.get('last_date'):
                    try:
                        last_purchase_date = customer['last_date'].strftime('%Y-%m-%d')
                    except AttributeError:
                        # Si last_date no es un objeto datetime
                        last_purchase_date = None

                # Asegurarse de que person_id sea string
                customer_id = str(customer['person_id']) if customer['person_id'] else None

                top_customers.append({
                    'customer_id': customer_id,
                    'customer_name': customer['person__full_name'] or 'Sin nombre',
                    'customer_document': customer['person__document'] or 'Sin documento',
                    'purchase_count': customer['count'] or 0,
                    'total_amount': float(customer['total'] or 0),
                    'avg_ticket': float(customer['avg'] or 0),
                    'last_purchase': last_purchase_date
                })
        except Exception as e:
            # Si hay algún error con los clientes, continuar sin ellos
            print(f"Error obteniendo top clientes: {e}")
            top_customers = []

        return {
            'daily_reports': daily_reports,
            'product_reports': product_reports,
            'stats': stats,
            'payment_methods': payment_methods,
            'top_customers': top_customers
        }


class OperationsMutation(graphene.ObjectType):
    person_mutation = PersonMutation.Field()
    create_operation = CreateOperation.Field()
    cancel_operation = CancelOperation.Field()
    create_person = CreatePerson.Field()
