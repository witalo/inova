from decimal import Decimal

# Create your views here.
from operations.apis import ApisNetPe
from operations.models import Operation

APIS_TOKEN = "Bearer apis-token-3244.1KWBKUSrgYq6HNht68arg8LNsId9vVLm"
api_net = ApisNetPe(APIS_TOKEN)


def generate_next_number(serial, company_id, operation_type):
    """Genera el siguiente número correlativo para una serie"""
    last_operation = Operation.objects.filter(
        serial=serial.serial,
        company_id=company_id,
        operation_type=operation_type
    ).order_by('-number').first()

    if last_operation:
        return last_operation.number + 1
    return 1


def calculate_operation_totals(details, igv_percent=18):
    """Calcula los totales de una operación basado en sus detalles"""
    totals = {
        'total_taxable': Decimal('0'),
        'total_unaffected': Decimal('0'),
        'total_exempt': Decimal('0'),
        'total_free': Decimal('0'),
        'total_discount': Decimal('0'),
        'total_igv': Decimal('0'),
        'total_amount': Decimal('0')
    }

    for detail in details:
        # Clasificar por tipo de afectación
        if detail.type_affectation.code == 10:  # Gravada
            totals['total_taxable'] += detail.total_value
            totals['total_igv'] += detail.total_igv
        elif detail.type_affectation.code == 20:  # Exonerada
            totals['total_exempt'] += detail.total_value
        elif detail.type_affectation.code == 30:  # Inafecta
            totals['total_unaffected'] += detail.total_value
        else:  # Gratuita
            totals['total_free'] += detail.total_value

        totals['total_discount'] += detail.total_discount

    # Total general
    totals['total_amount'] = (
            totals['total_taxable'] +
            totals['total_exempt'] +
            totals['total_unaffected'] +
            totals['total_igv']
    )

    return totals

