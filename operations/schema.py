from datetime import datetime

import graphene
from django.db.models import Q, Count, Sum

from operations import models
from operations.models import Person
from operations.mutations import PersonMutation, CreateOperation, CancelOperation, CreatePerson
from operations.types import *


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
    def resolve_search_person(root, info, document):
        return Person.objects.filter(
            Q(document__icontains=document) |
            Q(full_name__icontains=document)
        )[:10]

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
