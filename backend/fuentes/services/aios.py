"""
Analizador de la página "Boletín Estadístico AIOS".

La página lista los boletines semestrales como enlaces con texto del tipo
"Boletín AIOS Diciembre 2025 ( 392 KB )". Se identifican por ese texto
(no por la extensión), así el analizador sigue funcionando aunque cambie
el formato del archivo o la ruta donde se aloja.

Cada recurso devuelto es un diccionario:
    {
        "fuente": "aios",
        "nombre": "Boletín AIOS Diciembre 2025",
        "url": "https://www.aiosfp.org/...",
        "periodo": "2025-12",
        "anio": 2025,
        "mes": 12,
        "tipo": "xlsx",              # "desconocido" si la URL no trae extensión
        "tamano_texto": "392 KB",    # None si no aparece en el enlace
    }
"""
import logging
import re
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from fuentes.configuracion import AIOS, EXTENSIONES_PERMITIDAS
from fuentes.services.acceso_web import acceder_pagina

logger = logging.getLogger(__name__)

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# "Boletín AIOS Diciembre 2025" y variantes ("Diciembre2020" sin espacio)
_PATRON_BOLETIN = re.compile(
    r"Bolet[ií]n\s+AIOS\s+(" + "|".join(MESES) + r")\s*(\d{4})",
    re.IGNORECASE,
)
_PATRON_TAMANO = re.compile(r"\(\s*([\d.,]+\s*[KMG]B)\s*\)", re.IGNORECASE)
_PREFIJOS_NO_DESCARGABLES = ("javascript:", "#", "mailto:")
_TIPOS_ARCHIVO = {e.lstrip(".") for e in EXTENSIONES_PERMITIDAS}


class ErrorAnalisisFuente(Exception):
    """La página se descargó, pero no tiene la estructura esperada."""


def analizar_html(html: str, url_base: str) -> list[dict]:
    """Extrae los boletines de un HTML ya descargado (no usa la red)."""
    documento = BeautifulSoup(html, "html.parser")
    recursos: list[dict] = []
    vistos: set[str] = set()

    for enlace in documento.find_all("a", href=True):
        texto = enlace.get_text(" ", strip=True)
        coincidencia = _PATRON_BOLETIN.search(texto)
        if not coincidencia:
            continue

        href = enlace["href"].strip()
        if href.lower().startswith(_PREFIJOS_NO_DESCARGABLES):
            continue

        url = urljoin(url_base, href)
        if url in vistos:
            continue
        vistos.add(url)

        mes = MESES[coincidencia.group(1).lower()]
        anio = int(coincidencia.group(2))
        tamano = _PATRON_TAMANO.search(texto)
        extension = PurePosixPath(urlparse(url).path).suffix.lower().lstrip(".")

        recursos.append(
            {
                "fuente": AIOS.codigo,
                "nombre": f"Boletín AIOS {coincidencia.group(1).capitalize()} {anio}",
                "url": url,
                "periodo": f"{anio}-{mes:02d}",
                "anio": anio,
                "mes": mes,
                "tipo": extension if extension in _TIPOS_ARCHIVO else "desconocido",
                "tamano_texto": tamano.group(1).strip() if tamano else None,
            }
        )

    # Más recientes primero
    recursos.sort(key=lambda r: r["periodo"], reverse=True)
    return recursos


def descubrir_boletines(sesion=None) -> list[dict]:
    """Descarga la página de AIOS y devuelve los boletines disponibles."""
    pagina = acceder_pagina(AIOS.url, sesion)
    recursos = analizar_html(pagina["contenido_html"], pagina["url_final"])

    if not recursos:
        raise ErrorAnalisisFuente(
            "No se encontraron boletines en la página de AIOS; "
            "es posible que su estructura haya cambiado."
        )

    logger.info("AIOS: %d boletines encontrados.", len(recursos))
    return recursos