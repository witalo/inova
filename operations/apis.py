import requests
import logging
from typing import List, Optional


class ApisNetPe:
    BASE_URL = "https://api.apis.net.pe"

    def __init__(self, token: str = None) -> None:
        self.token = token

    def _get(self, path: str, params: dict):

        url = f"{self.BASE_URL}{path}"

        headers = {
            "Authorization": self.token,
            "Referer": "https://apis.net.pe/api-tipo-cambio.html"
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            if data:
                if data.get('tipoDocumento') == '1':
                    context = {
                        'success': True,
                        'nombres': data.get('nombres'),
                        'paterno': data.get('apellidoPaterno'),
                        'materno': data.get('apellidoMaterno'),
                        'direccion': data.get('direccion')
                    }
                    return context
                elif data.get('tipoDocumento') == '6':
                    context = {
                        'success': True,
                        'razon_social': data.get('nombre'),
                        'ruc': data.get('numeroDocumento'),
                        'direccion_completa': data.get('direccion'),
                        'estado': data.get('estado'),
                        'condicion': data.get('condicion'),
                        'ubigeo': data.get('ubigeo'),
                        'departamento': data.get('departamento'),
                        'provincia': data.get('provincia'),
                        'distrito': data.get('distrito'),
                    }
                    return context
                elif data.get('venta'):
                    context = {
                        'success': True,
                        'compra': data.get('compra'),
                        'venta': data.get('venta'),
                        'moneda': data.get('moneda')
                    }
                    return context
            else:
                context = {
                    'success': False
                }
                return context
        elif response.status_code == 422:
            logging.warning(f"{response.url} - parámetro inválido")
            logging.warning(response.text)
        elif response.status_code == 403:
            logging.warning(f"{response.url} - IP bloqueada")
        elif response.status_code == 429:
            logging.warning(f"{response.url} - Muchas solicitudes agregan retraso")
        elif response.status_code == 401:
            logging.warning(f"{response.url} - Token no válido o limitado")
        else:
            logging.warning(f"{response.url} - Server Error status_code={response.status_code}")
        return None

    def get_person(self, dni: str) -> Optional[dict]:
        return self._get("/v2/dni", {"numero": dni})

    def get_company(self, ruc: str) -> Optional[dict]:
        return self._get("/v2/ruc", {"numero": ruc})

    def get_exchange_rate(self, date: str) -> dict:
        return self._get("/v2/tipo-cambio-sunat", {"fecha": date})

    def get_exchange_rate_today(self) -> dict:
        return self._get("/v2/tipo-cambio-sunat", {})

    def get_exchange_rate_for_month(self, month: int, year: int) -> List[dict]:
        return self._get("/v2/tipo-cambio-sunat", {"month": month, "year": year})
