import graphene
from django.db import transaction
from django.db.models import Q, Count, Sum
import logging
from operations import models
from operations.apis import ApisNetPe
from operations.models import Person
from operations.mutations import PersonMutation, CreateOperation, CancelOperation, CreatePerson
from operations.types import *
from django.conf import settings
from datetime import datetime
import requests
# Configurar logger
logger = logging.getLogger(__name__)


class OperationsQuery(graphene.ObjectType):
    # Documentos
    documents = graphene.List(DocumentType)
    serials_by_document = graphene.List(
        SerialType,
        document_id=graphene.ID(required=True)
    )

    # Operaciones
    operations_by_date = graphene.List(
        OperationType,
        company_id=graphene.ID(required=True),
        date=graphene.String(required=True)
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

    @staticmethod
    def resolve_documents(root, info):
        return Document.objects.all().order_by('code')

    @staticmethod
    def resolve_serials_by_document(root, info, document_id):
        return Serial.objects.filter(document_id=document_id).order_by('serial')

    @staticmethod
    def resolve_operations_by_date(root, info, company_id, date):
        operation_date = datetime.strptime(date, '%Y-%m-%d').date()
        return Operation.objects.filter(
            company_id=company_id,
            operation_date=operation_date
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

    @staticmethod
    def resolve_sales_summary(root, info, company_id, start_date, end_date):
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()

        operations = Operation.objects.filter(
            company_id=company_id,
            operation_date__range=[start, end],
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
            operation_date__range=[start, end]
        ).select_related('document', 'person', 'user')

        if operation_type:
            queryset = queryset.filter(operation_type=operation_type)

        return queryset.order_by('-operation_date', '-created_at')

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


class OperationsMutation(graphene.ObjectType):
    person_mutation = PersonMutation.Field()
    create_operation = CreateOperation.Field()
    cancel_operation = CancelOperation.Field()
    create_person = CreatePerson.Field()
