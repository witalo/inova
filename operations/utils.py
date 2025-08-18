# ================================
# 16. UTILS Y HELPERS
# ================================

# operations/utils.py
from decimal import Decimal
import hashlib
import base64
from datetime import datetime


class BillingUtils:
    """Utilidades para facturación electrónica"""

    @staticmethod
    def calculate_hash(content):
        """Calcular hash de contenido"""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def format_amount(amount):
        """Formatear monto para XML"""
        if isinstance(amount, str):
            amount = Decimal(amount)
        return f"{amount:.2f}"

    @staticmethod
    def generate_filename(company_ruc, document_code, serial, number):
        """Generar nombre de archivo estándar"""
        return f"{company_ruc}-{document_code}-{serial}-{number:08d}"

    @staticmethod
    def validate_ruc(ruc):
        """Validar formato de RUC"""
        if not ruc or len(ruc) != 11:
            return False

        if not ruc.isdigit():
            return False

        # Algoritmo de validación de RUC
        weights = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(int(ruc[i]) * weights[i] for i in range(10))
        remainder = total % 11
        check_digit = 11 - remainder if remainder >= 2 else remainder

        return int(ruc[10]) == check_digit

    @staticmethod
    def validate_document_number(doc_type, doc_number):
        """Validar documento de identidad"""
        if doc_type == '1':  # DNI
            return len(doc_number) == 8 and doc_number.isdigit()
        elif doc_type == '6':  # RUC
            return BillingUtils.validate_ruc(doc_number)
        return True  # Otros tipos



class ErrorCodes:
    """Códigos de error estándar"""

    SUNAT_ERRORS = {
        '0': 'Procesado correctamente',
        '100': 'Error en validación de datos',
        '200': 'Error en estructura XML',
        '300': 'Error en firma digital',
        '400': 'Error en comunicación',
        '500': 'Error interno del servidor',
        '1001': 'Documento ya fue enviado anteriormente',
        '1002': 'No existe el tipo de documento',
        '1003': 'Numero de serie invalido',
        '2000': 'Servidor no disponible',
        '2001': 'Servicio en mantenimiento',
    }

    @classmethod
    def get_error_description(cls, code):
        """Obtener descripción de código de error"""
        return cls.SUNAT_ERRORS.get(str(code), f'Error desconocido: {code}')