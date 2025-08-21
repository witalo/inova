# ================================
# 5. SERVICIO DE ANULACIÓN
# ================================
# operations/services/cancellation_service.py
import base64
import os
import zipfile
import requests
from decimal import Decimal
from lxml import etree
from django.conf import settings
from django.utils import timezone
import logging
from datetime import datetime

from operations.views import get_peru_date

logger = logging.getLogger(__name__)


class CancellationService:
    """Servicio completo para anulación de comprobantes electrónicos"""

    def __init__(self, operation):
        self.operation = operation
        self.company = operation.company
        from .billing_service import BillingConfiguration, BillingFileManager
        self.config = BillingConfiguration()
        self.file_manager = BillingFileManager

    def cancel_document(self, reason_code='01', description='Anulación de la operación'):
        """
        Anular documento electrónico según su tipo

        reason_code:
            01: Anulación de la operación
            02: Anulación por error en el RUC
            03: Anulación por error en la descripción
            04: Descuento global
            05: Bonificación
            06: Devolución total
            07: Devolución parcial
            08: Otros conceptos
        """
        try:
            logger.info(f"=== INICIANDO ANULACIÓN ===")
            logger.info(f"Documento: {self.operation.serial}-{self.operation.number}")
            logger.info(f"Tipo: {self.operation.document.code if self.operation.document else '03'}")
            logger.info(f"Estado actual: {self.operation.billing_status}")

            # ⚠️ VALIDACIÓN MEJORADA: Permitir PROCESSING_CANCELLATION como estado válido
            valid_states = ['ACCEPTED', 'ACCEPTED_WITH_OBSERVATIONS', 'PROCESSING_CANCELLATION']

            if self.operation.billing_status not in valid_states:
                error_msg = f"Solo se pueden anular documentos aceptados por SUNAT. Estado actual: {self.operation.billing_status}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            # ⚠️ VALIDACIÓN MEJORADA: Verificar datos del cliente
            if not self.operation.person:
                logger.warning("Operación sin persona asociada, usando datos por defecto para cliente varios")

            # Determinar tipo de documento
            doc_type = self.operation.document.code if self.operation.document else '03'

            # Actualizar datos de anulación
            self.operation.cancellation_reason = reason_code
            self.operation.cancellation_description = description
            self.operation.cancellation_date = get_peru_date()

            # Solo cambiar a PROCESSING_CANCELLATION si no está ya en ese estado
            if self.operation.billing_status != 'PROCESSING_CANCELLATION':
                self.operation.billing_status = 'PROCESSING_CANCELLATION'

            self.operation.save()

            # Determinar proceso según tipo de documento
            if doc_type in ['01', '07', '08']:  # Facturas y Notas
                logger.info("Procesando COMUNICACIÓN DE BAJA (Facturas/Notas)")
                return self._process_voided_documents(reason_code, description)
            elif doc_type == '03':  # Boletas
                logger.info("Procesando RESUMEN DIARIO (Boletas)")
                return self._process_summary_documents(reason_code, description)
            else:
                raise ValueError(f"Tipo de documento no soportado para anulación: {doc_type}")

        except Exception as e:
            logger.error(f"Error en anulación: {str(e)}")
            self.operation.billing_status = 'CANCELLATION_ERROR'
            self.operation.sunat_error_description = str(e)
            self.operation.save()
            raise

    def _process_voided_documents(self, reason_code, description):
        """Procesar Comunicación de Baja para Facturas y Notas"""
        try:
            # Generar XML de comunicación de baja
            xml_path = self._generate_voided_xml(reason_code, description)

            # Firmar XML
            signed_xml_path = self._sign_cancellation_xml(xml_path)

            # Enviar a SUNAT (devuelve ticket)
            ticket = self._send_summary_to_sunat(signed_xml_path)

            if ticket:
                self.operation.cancellation_ticket = ticket
                self.operation.billing_status = 'CANCELLATION_PENDING'
                self.operation.save()

                logger.info(f"Comunicación de baja enviada. Ticket: {ticket}")

                # Consultar estado del ticket inmediatamente
                return self._check_ticket_status(ticket)
            else:
                raise Exception("No se recibió ticket de SUNAT")

        except Exception as e:
            logger.error(f"Error en comunicación de baja: {str(e)}")
            raise

    def _process_summary_documents(self, reason_code, description):
        """Procesar Resumen Diario para Boletas"""
        try:
            # Generar XML de resumen diario
            xml_path = self._generate_summary_xml(reason_code, description)

            # Firmar XML
            signed_xml_path = self._sign_cancellation_xml(xml_path)

            # Enviar a SUNAT (devuelve ticket)
            ticket = self._send_summary_to_sunat(signed_xml_path)

            if ticket:
                self.operation.cancellation_ticket = ticket
                self.operation.billing_status = 'CANCELLATION_PENDING'
                self.operation.save()

                logger.info(f"Resumen diario enviado. Ticket: {ticket}")

                # Consultar estado del ticket
                return self._check_ticket_status(ticket)
            else:
                raise Exception("No se recibió ticket de SUNAT")

        except Exception as e:
            logger.error(f"Error en resumen diario: {str(e)}")
            raise

    def _generate_voided_xml(self, reason_code, description):
        """Generar XML de Comunicación de Baja (para Facturas y Notas)"""
        current_date = get_peru_date()
        correlative = self._get_next_cancellation_correlative('RA')

        filename = f"{self.company.ruc}-RA-{current_date.strftime('%Y%m%d')}-{correlative:05d}"

        xml_content = f'''<?xml version="1.0" encoding="ISO-8859-1"?>
<VoidedDocuments xmlns="urn:sunat:names:specification:ubl:peru:schema:xsd:VoidedDocuments-1" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
<ext:UBLExtensions>
<ext:UBLExtension>
<ext:ExtensionContent></ext:ExtensionContent>
</ext:UBLExtension>
</ext:UBLExtensions>
<cbc:UBLVersionID>2.0</cbc:UBLVersionID>
<cbc:CustomizationID>1.0</cbc:CustomizationID>
<cbc:ID>RA-{current_date.strftime('%Y%m%d')}-{correlative:05d}</cbc:ID>
<cbc:ReferenceDate>{self.operation.emit_date}</cbc:ReferenceDate>
<cbc:IssueDate>{current_date}</cbc:IssueDate>
<cac:Signature>
<cbc:ID>{self.company.ruc}</cbc:ID>
<cac:SignatoryParty>
<cac:PartyIdentification>
<cbc:ID>{self.company.ruc}</cbc:ID>
</cac:PartyIdentification>
<cac:PartyName>
<cbc:Name>{self.company.denomination}</cbc:Name>
</cac:PartyName>
</cac:SignatoryParty>
<cac:DigitalSignatureAttachment>
<cac:ExternalReference>
<cbc:URI>{self.company.ruc}</cbc:URI>
</cac:ExternalReference>
</cac:DigitalSignatureAttachment>
</cac:Signature>
<cac:AccountingSupplierParty>
<cbc:CustomerAssignedAccountID>{self.company.ruc}</cbc:CustomerAssignedAccountID>
<cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>
<cac:Party>
<cac:PartyLegalEntity>
<cbc:RegistrationName>{self.company.denomination}</cbc:RegistrationName>
</cac:PartyLegalEntity>
</cac:Party>
</cac:AccountingSupplierParty>
<sac:VoidedDocumentsLine>
<cbc:LineID>1</cbc:LineID>
<cbc:DocumentTypeCode>{self.operation.document.code if self.operation.document else '03'}</cbc:DocumentTypeCode>
<sac:DocumentSerialID>{self.operation.serial}</sac:DocumentSerialID>
<sac:DocumentNumberID>{self.operation.number}</sac:DocumentNumberID>
<sac:VoidReasonDescription>{description}</sac:VoidReasonDescription>
</sac:VoidedDocumentsLine>
</VoidedDocuments>'''

        # Guardar XML
        xml_path = self.file_manager.get_file_path(
            self.company.ruc, 'BAJA/XML', f"{filename}.xml"
        )

        os.makedirs(os.path.dirname(xml_path), exist_ok=True)
        with open(xml_path, 'w', encoding='iso-8859-1') as f:
            f.write(xml_content)
        # ⚠️ GUARDAR RUTA EN LA OPERACIÓN
        self.operation.cancellation_xml_path = xml_path
        self.operation.save()

        logger.info(f"XML de baja generado: {filename}.xml")
        return xml_path

    def _generate_summary_xml(self, reason_code, description):
        """Generar XML de Resumen Diario (para Boletas) - CORREGIDO"""
        current_date = get_peru_date()
        correlative = self._get_next_cancellation_correlative('RC')

        filename = f"{self.company.ruc}-RC-{current_date.strftime('%Y%m%d')}-{correlative:05d}"

        # Calcular totales
        total_amount = Decimal(str(self.operation.total_amount))
        taxable_amount = Decimal(str(self.operation.total_taxable))
        igv_amount = Decimal(str(self.operation.igv_amount))

        # Estado: 3 = Anulado
        status = '3'

        # ⚠️ CORRECCIÓN: Cerrar correctamente las etiquetas XML
        xml_content = f'''<?xml version="1.0" encoding="ISO-8859-1"?>
<SummaryDocuments xmlns="urn:sunat:names:specification:ubl:peru:schema:xsd:SummaryDocuments-1" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2" xmlns:sac="urn:sunat:names:specification:ubl:peru:schema:xsd:SunatAggregateComponents-1" xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
<ext:UBLExtensions>
<ext:UBLExtension>
<ext:ExtensionContent></ext:ExtensionContent>
</ext:UBLExtension>
</ext:UBLExtensions>
<cbc:UBLVersionID>2.0</cbc:UBLVersionID>
<cbc:CustomizationID>1.1</cbc:CustomizationID>
<cbc:ID>RC-{current_date.strftime('%Y%m%d')}-{correlative:05d}</cbc:ID>
<cbc:ReferenceDate>{self.operation.emit_date}</cbc:ReferenceDate>
<cbc:IssueDate>{current_date}</cbc:IssueDate>
<cac:Signature>
<cbc:ID>{self.company.ruc}</cbc:ID>
<cac:SignatoryParty>
<cac:PartyIdentification>
<cbc:ID>{self.company.ruc}</cbc:ID>
</cac:PartyIdentification>
<cac:PartyName>
<cbc:Name>{self.company.denomination}</cbc:Name>
</cac:PartyName>
</cac:SignatoryParty>
<cac:DigitalSignatureAttachment>
<cac:ExternalReference>
<cbc:URI>{self.company.ruc}</cbc:URI>
</cac:ExternalReference>
</cac:DigitalSignatureAttachment>
</cac:Signature>
<cac:AccountingSupplierParty>
<cbc:CustomerAssignedAccountID>{self.company.ruc}</cbc:CustomerAssignedAccountID>
<cbc:AdditionalAccountID>6</cbc:AdditionalAccountID>
<cac:Party>
<cac:PartyLegalEntity>
<cbc:RegistrationName>{self.company.denomination}</cbc:RegistrationName>
</cac:PartyLegalEntity>
</cac:Party>
</cac:AccountingSupplierParty>
<sac:SummaryDocumentsLine>
<cbc:LineID>1</cbc:LineID>
<cbc:DocumentTypeCode>03</cbc:DocumentTypeCode>
<cbc:ID>{self.operation.serial}-{self.operation.number}</cbc:ID>
<cac:AccountingCustomerParty>
<cbc:CustomerAssignedAccountID>{self._get_customer_document()}</cbc:CustomerAssignedAccountID>
<cbc:AdditionalAccountID>{self._get_customer_doc_type()}</cbc:AdditionalAccountID>
</cac:AccountingCustomerParty>
<cac:Status>
<cbc:ConditionCode>{status}</cbc:ConditionCode>
</cac:Status>
<sac:TotalAmount currencyID="{self.operation.currency}">{self._format_decimal(total_amount)}</sac:TotalAmount>
<sac:BillingPayment>
<cbc:PaidAmount currencyID="{self.operation.currency}">{self._format_decimal(total_amount)}</cbc:PaidAmount>
<cbc:InstructionID>01</cbc:InstructionID>
</sac:BillingPayment>
<cac:TaxTotal>
<cbc:TaxAmount currencyID="{self.operation.currency}">{self._format_decimal(igv_amount)}</cbc:TaxAmount>
<cac:TaxSubtotal>
<cbc:TaxableAmount currencyID="{self.operation.currency}">{self._format_decimal(taxable_amount)}</cbc:TaxableAmount>
<cbc:TaxAmount currencyID="{self.operation.currency}">{self._format_decimal(igv_amount)}</cbc:TaxAmount>
<cac:TaxCategory>
<cac:TaxScheme>
<cbc:ID>1000</cbc:ID>
<cbc:Name>IGV</cbc:Name>
<cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
</cac:TaxScheme>
</cac:TaxCategory>
</cac:TaxSubtotal>
</cac:TaxTotal>
</sac:SummaryDocumentsLine>
</SummaryDocuments>'''

        # Guardar XML
        xml_path = self.file_manager.get_file_path(
            self.company.ruc, 'BAJA/XML', f"{filename}.xml"
        )

        os.makedirs(os.path.dirname(xml_path), exist_ok=True)
        with open(xml_path, 'w', encoding='iso-8859-1') as f:
            f.write(xml_content)
        # ⚠️ GUARDAR RUTA EN LA OPERACIÓN
        self.operation.cancellation_xml_path = xml_path
        self.operation.save()
        logger.info(f"XML de resumen generado: {filename}.xml")

        # Validar XML generado
        try:
            with open(xml_path, 'r', encoding='iso-8859-1') as f:
                etree.parse(f)
            logger.info(f"XML válido: {filename}.xml")
        except etree.XMLSyntaxError as e:
            logger.error(f"XML inválido: {str(e)}")
            raise ValueError(f"XML generado no es válido: {str(e)}")

        return xml_path

    def _get_customer_document(self):
        """
        Obtener documento del cliente de forma segura
        Returns '00000000' para clientes varios o sin documento
        """
        try:
            if (self.operation.person and
                    hasattr(self.operation.person, 'document') and
                    self.operation.person.document and
                    self.operation.person.document.strip()):

                doc = self.operation.person.document.strip()
                # Validar que no sea una cadena vacía o solo ceros
                if doc and doc != "0" * len(doc):
                    return doc
        except (AttributeError, TypeError):
            pass

        # Valor por defecto para clientes varios
        return "00000000"

    def _get_customer_doc_type(self):
        """
        Obtener tipo de documento del cliente de forma segura
        Returns '0' para clientes varios o sin documento específico
        """
        try:
            document = self._get_customer_document()

            # Si es el documento por defecto, retornar tipo 0
            if document == "00000000":
                return "0"

            # Determinar por longitud
            if len(document) == 8:
                return "1"  # DNI
            elif len(document) == 11:
                return "6"  # RUC

            # Intentar obtener del person_type si existe
            if (self.operation.person and
                    hasattr(self.operation.person, 'person_type') and
                    self.operation.person.person_type):
                return str(self.operation.person.person_type)

        except (AttributeError, TypeError, ValueError):
            pass

        # Valor por defecto
        return "0"

    def _get_person_doc_type(self):
        """Obtener tipo de documento del cliente"""
        return self._get_customer_doc_type()

    def _format_decimal(self, value, decimals=2):
        """Formatear decimal"""
        if value is None:
            return f"0.{'0' * decimals}"
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        return format(value, f'.{decimals}f')

    def _get_next_cancellation_correlative(self, prefix):
        """Obtener próximo correlativo de anulación"""
        from operations.models import Operation

        today = timezone.now().date()

        # Buscar último correlativo del día para el tipo de documento
        last_cancellation = Operation.objects.filter(
            company=self.company,
            cancellation_date=today
        ).exclude(cancellation_ticket__isnull=True).exclude(
            cancellation_ticket=''
        ).order_by('-id').first()

        if last_cancellation and last_cancellation.cancellation_ticket:
            # Extraer correlativo del ticket
            try:
                parts = last_cancellation.cancellation_ticket.split('-')
                if len(parts) >= 3:
                    last_number = int(parts[-1])
                    return last_number + 1
            except:
                pass

        return 1

    def _sign_cancellation_xml(self, xml_path):
        """Firmar XML de anulación"""
        from .billing_service import XMLSigner

        signer = XMLSigner(self.company)
        signed_path = signer.sign_xml(xml_path)

        # Mover a carpeta BAJA/FIRMA
        filename = os.path.basename(signed_path)
        final_path = self.file_manager.get_file_path(
            self.company.ruc, 'BAJA/FIRMA', filename
        )

        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        # Si el archivo ya está en el destino correcto, no hacer nada
        if signed_path != final_path:
            import shutil
            shutil.move(signed_path, final_path)

        # ⚠️ GUARDAR RUTA DEL XML FIRMADO
        self.operation.cancellation_signed_xml_path = final_path
        self.operation.save()

        logger.info(f"XML firmado: {filename}")
        return final_path

    def _send_summary_to_sunat(self, signed_xml_path):
        """Enviar resumen/baja a SUNAT y obtener ticket"""
        try:
            # Crear ZIP
            zip_path = self._create_zip(signed_xml_path)

            # Leer contenido
            with open(zip_path, 'rb') as f:
                zip_content = base64.b64encode(f.read()).decode()

            filename = os.path.basename(zip_path)

            # Configuración según ambiente
            if self.company.environment == 'BETA':
                wsdl_url = 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService'
                username = f"{self.company.ruc}MODDATOS"
                password = "moddatos"
            else:
                wsdl_url = 'https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService'
                username = f"{self.company.ruc}{self.company.sunat_username}"
                password = self.company.sunat_password

            # Construir SOAP para sendSummary
            soap_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.sunat.gob.pe" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
<soapenv:Header>
<wsse:Security>
<wsse:UsernameToken>
<wsse:Username>{username}</wsse:Username>
<wsse:Password>{password}</wsse:Password>
</wsse:UsernameToken>
</wsse:Security>
</soapenv:Header>
<soapenv:Body>
<ser:sendSummary>
<fileName>{filename}</fileName>
<contentFile>{zip_content}</contentFile>
</ser:sendSummary>
</soapenv:Body>
</soapenv:Envelope>'''

            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '""',
            }

            logger.info(f"Enviando resumen/baja a SUNAT: {filename}")

            response = requests.post(
                wsdl_url,
                data=soap_xml.encode('utf-8'),
                headers=headers,
                timeout=60,
                verify=True
            )

            if response.status_code == 200:
                # Extraer ticket de la respuesta
                import re
                ticket_pattern = r'<ticket>([^<]+)</ticket>'
                match = re.search(ticket_pattern, response.text)

                if match:
                    ticket = match.group(1)
                    logger.info(f"Ticket recibido: {ticket}")
                    return ticket
                else:
                    logger.error("No se encontró ticket en la respuesta")
                    logger.error(f"Respuesta: {response.text[:500]}")
                    raise Exception("No se recibió ticket de SUNAT")
            else:
                logger.error(f"Error HTTP {response.status_code}: {response.text[:500]}")
                raise Exception(f"Error enviando a SUNAT: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"Error enviando resumen/baja: {str(e)}")
            raise

    def _check_ticket_status(self, ticket):
        """Consultar estado del ticket en SUNAT"""
        try:
            logger.info(f"Consultando estado del ticket: {ticket}")

            # Configuración según ambiente
            if self.company.environment == 'BETA':
                wsdl_url = 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService'
                username = f"{self.company.ruc}MODDATOS"
                password = "moddatos"
            else:
                wsdl_url = 'https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService'
                username = f"{self.company.ruc}{self.company.sunat_username}"
                password = self.company.sunat_password

            # SOAP para getStatus
            soap_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.sunat.gob.pe" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
    <soapenv:Header>
    <wsse:Security>
    <wsse:UsernameToken>
    <wsse:Username>{username}</wsse:Username>
    <wsse:Password>{password}</wsse:Password>
    </wsse:UsernameToken>
    </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
    <ser:getStatus>
    <ticket>{ticket}</ticket>
    </ser:getStatus>
    </soapenv:Body>
    </soapenv:Envelope>'''

            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': '""',
            }

            # Esperar antes del primer intento para dar tiempo al ticket
            import time
            time.sleep(2)

            # Aumentar reintentos de 3 a 5
            max_attempts = 5

            for attempt in range(max_attempts):
                try:
                    response = requests.post(
                        wsdl_url,
                        data=soap_xml.encode('utf-8'),
                        headers=headers,
                        timeout=60,
                        verify=True
                    )

                    if response.status_code == 200:
                        # Buscar statusCode
                        import re
                        status_pattern = r'<statusCode>([^<]+)</statusCode>'
                        match = re.search(status_pattern, response.text)

                        if match:
                            status_code = match.group(1)
                            logger.info(f"Estado del ticket: {status_code}")

                            if status_code == '0':  # Procesado correctamente
                                # Buscar CDR en content
                                content_pattern = r'<content>([^<]+)</content>'
                                content_match = re.search(content_pattern, response.text)

                                if content_match:
                                    cdr_base64 = content_match.group(1)
                                    self._process_cancellation_cdr(cdr_base64)

                                self.operation.billing_status = 'CANCELLED'
                                self.operation.save()

                                logger.info("Documento anulado exitosamente en SUNAT")
                                return True

                            elif status_code == '98':  # En proceso
                                logger.info("⏳ Ticket aún en proceso, esperando...")
                                time.sleep(5)
                                continue

                            elif status_code == '99':  # Error
                                message_pattern = r'<statusMessage>([^<]+)</statusMessage>'
                                message_match = re.search(message_pattern, response.text)
                                error_msg = message_match.group(1) if message_match else f"Error código {status_code}"

                                logger.error(f"Error en SUNAT: {error_msg}")

                                self.operation.billing_status = 'CANCELLATION_ERROR'
                                self.operation.sunat_error_description = error_msg
                                self.operation.save()
                                raise Exception(f"Error en SUNAT: {error_msg}")
                        else:
                            logger.warning(f"No se encontró statusCode en intento {attempt + 1}/{max_attempts}")
                            if attempt < max_attempts - 1:
                                time.sleep(5)
                                continue

                    elif response.status_code == 401:
                        logger.warning(f"Error HTTP 401 (Autenticación) en intento {attempt + 1}/{max_attempts}")
                        if attempt < max_attempts - 1:
                            wait_time = 5 + (attempt * 2)
                            logger.info(f"   Esperando {wait_time} segundos antes de reintentar...")
                            time.sleep(wait_time)
                            continue
                        else:
                            self.operation.billing_status = 'CANCELLATION_ERROR'
                            self.operation.sunat_error_description = "Error de autenticación con SUNAT (401)"
                            self.operation.save()
                            raise Exception("Error de autenticación con SUNAT (401)")

                    elif response.status_code == 500:
                        logger.warning(f"Error HTTP 500 (Servidor) en intento {attempt + 1}/{max_attempts}")
                        if attempt < max_attempts - 1:
                            time.sleep(10)
                            continue
                        else:
                            self.operation.billing_status = 'CANCELLATION_ERROR'
                            self.operation.sunat_error_description = "Error del servidor SUNAT (500)"
                            self.operation.save()
                            raise Exception("Error del servidor SUNAT (500)")

                    else:
                        logger.error(f"Error HTTP {response.status_code}")
                        if attempt < max_attempts - 1:
                            time.sleep(5)
                            continue
                        else:
                            self.operation.billing_status = 'CANCELLATION_ERROR'
                            self.operation.sunat_error_description = f"Error HTTP {response.status_code}"
                            self.operation.save()

                except requests.exceptions.Timeout:
                    logger.warning(f"Timeout en intento {attempt + 1}/{max_attempts}")
                    if attempt < max_attempts - 1:
                        time.sleep(5)
                        continue
                    else:
                        self.operation.billing_status = 'CANCELLATION_ERROR'
                        self.operation.sunat_error_description = "Timeout al consultar SUNAT"
                        self.operation.save()
                        raise Exception("Timeout al consultar ticket en SUNAT")

                except requests.exceptions.ConnectionError:
                    logger.warning(f"Error de conexión en intento {attempt + 1}/{max_attempts}")
                    if attempt < max_attempts - 1:
                        time.sleep(10)
                        continue
                    else:
                        self.operation.billing_status = 'CANCELLATION_ERROR'
                        self.operation.sunat_error_description = "Error de conexión con SUNAT"
                        self.operation.save()
                        raise Exception("Error de conexión con SUNAT")

                except requests.exceptions.RequestException as e:
                    logger.warning(f"Error de request en intento {attempt + 1}/{max_attempts}: {str(e)}")
                    if attempt < max_attempts - 1:
                        time.sleep(5)
                        continue
                    else:
                        self.operation.billing_status = 'CANCELLATION_ERROR'
                        self.operation.sunat_error_description = f"Error de request: {str(e)}"
                        self.operation.save()
                        raise

            # Si llegamos aquí, no se pudo procesar después de todos los intentos
            logger.error(f"No se pudo verificar el estado del ticket después de {max_attempts} intentos")
            self.operation.billing_status = 'CANCELLATION_ERROR'
            self.operation.sunat_error_description = f"No se pudo verificar el estado después de {max_attempts} intentos"
            self.operation.save()
            return False

        except Exception as e:
            logger.error(f"Error consultando ticket: {str(e)}")
            # Solo actualizar si no se ha actualizado ya
            if self.operation.billing_status != 'CANCELLATION_ERROR':
                self.operation.billing_status = 'CANCELLATION_ERROR'
                self.operation.sunat_error_description = str(e)[:500]  # Limitar longitud
                self.operation.save()
            return False

    def _process_cancellation_cdr(self, cdr_base64):
        """Procesar CDR de anulación"""
        try:
            # Decodificar CDR
            cdr_content = base64.b64decode(cdr_base64)

            # Guardar CDR
            cdr_filename = f"R-{self.operation.cancellation_ticket}.zip"
            cdr_path = self.file_manager.get_file_path(
                self.company.ruc, 'BAJA/CDR', cdr_filename
            )

            os.makedirs(os.path.dirname(cdr_path), exist_ok=True)
            with open(cdr_path, 'wb') as f:
                f.write(cdr_content)

            logger.info(f"CDR de anulación guardado: {cdr_filename}")

            # ⚠️ ACTUALIZAR OPERACIÓN CON TODAS LAS RUTAS
            self.operation.cancellation_cdr_path = cdr_path
            self.operation.save()

        except Exception as e:
            logger.error(f"Error procesando CDR de anulación: {str(e)}")

    def _create_zip(self, xml_path):
        """Crear ZIP del XML"""
        xml_filename = os.path.basename(xml_path)
        zip_filename = xml_filename.replace('.xml', '.zip')
        zip_path = xml_path.replace('.xml', '.zip')

        if os.path.exists(zip_path):
            os.remove(zip_path)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(xml_path, xml_filename)

        logger.info(f"ZIP creado: {zip_filename}")
        return zip_path


# Función helper para anular múltiples documentos
def bulk_cancel_documents(operation_ids, reason_code='01', description='Anulación masiva'):
    """
    Anular múltiples documentos

    Args:
        operation_ids: Lista de IDs de operaciones a anular
        reason_code: Código de motivo de anulación
        description: Descripción de la anulación

    Returns:
        Diccionario con resultados
    """
    from operations.models import Operation

    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }

    for op_id in operation_ids:
        try:
            operation = Operation.objects.get(id=op_id)

            # Verificar si puede anularse
            if operation.billing_status not in ['ACCEPTED', 'ACCEPTED_WITH_OBSERVATIONS']:
                results['skipped'].append({
                    'id': op_id,
                    'document': f"{operation.serial}-{operation.number}",
                    'reason': f'Estado no válido: {operation.billing_status}'
                })
                continue

            # Anular
            service = CancellationService(operation)
            if service.cancel_document(reason_code, description):
                results['success'].append({
                    'id': op_id,
                    'document': f"{operation.serial}-{operation.number}"
                })
            else:
                results['failed'].append({
                    'id': op_id,
                    'document': f"{operation.serial}-{operation.number}",
                    'error': operation.sunat_error_description
                })

        except Operation.DoesNotExist:
            results['failed'].append({
                'id': op_id,
                'error': 'Operación no encontrada'
            })
        except Exception as e:
            results['failed'].append({
                'id': op_id,
                'error': str(e)
            })

    logger.info(f"Anulación masiva completada: {len(results['success'])} exitosas, "
                f"{len(results['failed'])} fallidas, {len(results['skipped'])} omitidas")

    return results


# Tarea para verificar tickets pendientes (si usas Celery)
def check_pending_cancellation_tickets():
    """
    Verificar tickets de anulación pendientes
    Esta función puede ejecutarse periódicamente para verificar tickets
    """
    from operations.models import Operation

    pending_operations = Operation.objects.filter(
        billing_status='CANCELLATION_PENDING',
        cancellation_ticket__isnull=False
    ).exclude(cancellation_ticket='')

    for operation in pending_operations:
        try:
            service = CancellationService(operation)
            service._check_ticket_status(operation.cancellation_ticket)
        except Exception as e:
            logger.error(f"Error verificando ticket {operation.cancellation_ticket}: {str(e)}")
