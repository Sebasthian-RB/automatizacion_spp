"""
Acceso HTTP a las páginas de las fuentes (SBS, AIOS).

Responsabilidades de este módulo:
  - crear una sesión HTTP con reintentos y certificados del sistema (Windows),
  - descargar una página y validar la respuesta,
  - devolver un resumen estructurado (enlaces, formularios, iframes, HTML).

No interpreta el contenido de cada fuente: eso lo hacen los analizadores.
"""
import logging
import ssl
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fuentes.configuracion import (
    CODIGOS_REINTENTABLES,
    FACTOR_ESPERA_REINTENTOS,
    HEADERS,
    MAX_REINTENTOS,
    TIMEOUT,
)

try:
    import truststore
except ImportError:  # pragma: no cover
    truststore = None

logger = logging.getLogger(__name__)


class AccesoWebError(Exception):
    """Error al acceder a una página web de una fuente."""


# ---------------------------------------------------------------------------
# Sesión HTTP
# ---------------------------------------------------------------------------
def _crear_contexto_ssl() -> ssl.SSLContext:
    """Usa el almacén de certificados del sistema si truststore está instalado."""
    if truststore is not None:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    logger.warning("truststore no está instalado; se usan los certificados de certifi.")
    return ssl.create_default_context()


class AdaptadorCertificadosWindows(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["ssl_context"] = _crear_contexto_ssl()
        super().init_poolmanager(connections, maxsize, block, **pool_kwargs)


def crear_sesion() -> requests.Session:
    """Sesión con cabeceras de navegador, reintentos y certificados del sistema."""
    reintentos = Retry(
        total=MAX_REINTENTOS,
        backoff_factor=FACTOR_ESPERA_REINTENTOS,
        status_forcelist=CODIGOS_REINTENTABLES,
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    sesion = requests.Session()
    sesion.headers.update(HEADERS)
    sesion.mount("https://", AdaptadorCertificadosWindows(max_retries=reintentos))
    sesion.mount("http://", HTTPAdapter(max_retries=reintentos))
    return sesion


# ---------------------------------------------------------------------------
# Descarga de páginas
# ---------------------------------------------------------------------------
def _corregir_codificacion(respuesta: requests.Response) -> None:
    """Si el servidor no declara charset, requests asume ISO-8859-1 y rompe las tildes."""
    tipo = respuesta.headers.get("Content-Type", "").lower()
    if "charset" not in tipo:
        respuesta.encoding = respuesta.apparent_encoding


def obtener_respuesta(url: str, sesion: requests.Session | None = None) -> requests.Response:
    """GET con validación. Lanza AccesoWebError con un mensaje claro si falla."""
    sesion_propia = sesion is None
    sesion = sesion or crear_sesion()
    try:
        respuesta = sesion.get(url, timeout=TIMEOUT)
        respuesta.raise_for_status()
    except requests.exceptions.SSLError as exc:
        raise AccesoWebError(f"Error de certificado SSL al acceder a {url}") from exc
    except requests.exceptions.Timeout as exc:
        raise AccesoWebError(f"Tiempo de espera agotado al acceder a {url}") from exc
    except requests.exceptions.HTTPError as exc:
        codigo = exc.response.status_code if exc.response is not None else "?"
        raise AccesoWebError(f"El servidor respondió HTTP {codigo} en {url}") from exc
    except requests.exceptions.RequestException as exc:
        raise AccesoWebError(f"No se pudo acceder a {url}: {exc}") from exc
    finally:
        if sesion_propia:
            sesion.close()

    _corregir_codificacion(respuesta)
    return respuesta


def acceder_pagina(url: str, sesion: requests.Session | None = None) -> dict:
    """Descarga una página y devuelve un resumen estructurado de su contenido."""
    respuesta = obtener_respuesta(url, sesion)
    documento = BeautifulSoup(respuesta.text, "html.parser")
    url_final = respuesta.url

    enlaces = [
        {
            "texto": enlace.get_text(" ", strip=True),
            "url": enlace["href"],
            "url_absoluta": urljoin(url_final, enlace["href"]),
        }
        for enlace in documento.find_all("a", href=True)
    ]

    formularios = [
        {
            "accion": formulario.get("action", ""),
            "metodo": formulario.get("method", "get").upper(),
        }
        for formulario in documento.find_all("form")
    ]

    iframes = [
        urljoin(url_final, iframe["src"])
        for iframe in documento.find_all("iframe", src=True)
    ]

    return {
        "url_solicitada": url,
        "url_final": url_final,
        "codigo_http": respuesta.status_code,
        "titulo": documento.title.get_text(strip=True) if documento.title else "Sin título",
        "texto_visible": documento.get_text(" ", strip=True)[:2500],
        "enlaces": enlaces,
        "formularios": formularios,
        "iframes": iframes,
        "scripts": len(documento.find_all("script")),
        # True si la página es ASP.NET con estado (requiere postback para algunos datos)
        "usa_viewstate": documento.find("input", {"name": "__VIEWSTATE"}) is not None,
        "contenido_html": respuesta.text,
    }