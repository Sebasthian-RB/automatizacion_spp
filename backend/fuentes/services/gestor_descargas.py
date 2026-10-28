"""
Descarga de los recursos encontrados por los analizadores.

Un "recurso" es el diccionario que devuelven los analizadores, como mínimo con:
    {"fuente": "aios", "url": "https://...", "periodo": "2025-12"}

El nombre y el tipo del archivo se leen de las cabeceras de la respuesta
(Content-Disposition / Content-Type) y, si faltan, del propio contenido,
porque muchas URLs no terminan en la extensión real del archivo.
"""
import logging
import os
import re
from email.message import Message
from pathlib import Path

import requests

from fuentes.configuracion import (
    EXTENSIONES_PERMITIDAS,
    TAMANO_MAXIMO_BYTES,
    TIMEOUT,
    obtener_fuente,
)
from fuentes.services.acceso_web import crear_sesion
from fuentes.services.validacion_archivos import (
    ErrorValidacionArchivo,
    detectar_extension,
    validar_archivo,
)

logger = logging.getLogger(__name__)

TAMANO_BLOQUE = 64 * 1024

_EXTENSION_POR_MIME = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel.sheet.macroenabled.12": ".xlsm",
    "application/vnd.ms-excel": ".xls",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "text/csv": ".csv",
}


class ErrorDescarga(Exception):
    """No se pudo descargar o validar un recurso."""


def _nombre_seguro(nombre: str) -> str:
    """Elimina caracteres no válidos en nombres de archivo de Windows."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nombre).strip(". ")


def _nombre_desde_cabeceras(respuesta: requests.Response) -> str | None:
    cabecera = respuesta.headers.get("Content-Disposition")
    if not cabecera:
        return None
    mensaje = Message()
    mensaje["content-disposition"] = cabecera
    return mensaje.get_filename()


def _base_y_extension(respuesta: requests.Response, recurso: dict) -> tuple[str, str | None]:
    """Nombre sin extensión y extensión (None si aún no se puede saber)."""
    nombre = _nombre_desde_cabeceras(respuesta)
    if nombre:
        base, extension = Path(nombre).stem, Path(nombre).suffix.lower()
    else:
        base = f"{recurso['fuente']}_{recurso.get('periodo', 'recurso')}"
        extension = ""

    if extension not in EXTENSIONES_PERMITIDAS:
        tipo = respuesta.headers.get("Content-Type", "").split(";")[0].strip().lower()
        extension = _EXTENSION_POR_MIME.get(tipo)

    return _nombre_seguro(base) or "recurso", extension


def _resumen(estado: str, destino: Path, validacion: dict, recurso: dict) -> dict:
    return {
        "estado": estado,
        "fuente": recurso["fuente"],
        "periodo": recurso.get("periodo"),
        "url": recurso["url"],
        "ruta": str(destino),
        "nombre": destino.name,
        "extension": validacion["extension"],
        "tamano_bytes": validacion["tamano_bytes"],
        "hojas": validacion["hojas"],
    }


def descargar_recurso(
    recurso: dict,
    sesion: requests.Session | None = None,
    forzar: bool = False,
) -> dict:
    """
    Descarga un recurso en la carpeta de su fuente y lo valida.

    Si el archivo ya existe y es válido, no lo descarga de nuevo (salvo forzar=True).
    Lanza ErrorDescarga si algo falla; nunca deja archivos a medias.
    """
    fuente = obtener_fuente(recurso["fuente"])
    fuente.carpeta.mkdir(parents=True, exist_ok=True)
    url = recurso["url"]

    sesion_propia = sesion is None
    sesion = sesion or crear_sesion()
    temporal = None
    try:
        with sesion.get(url, timeout=TIMEOUT, stream=True) as respuesta:
            respuesta.raise_for_status()

            tipo = respuesta.headers.get("Content-Type", "").lower()
            if tipo.startswith("text/html"):
                raise ErrorDescarga(f"{url} devolvió una página HTML, no un archivo.")

            base, extension = _base_y_extension(respuesta, recurso)

            # ¿Ya lo tenemos?
            if extension and not forzar:
                existente = fuente.carpeta / f"{base}{extension}"
                if existente.exists():
                    try:
                        validacion = validar_archivo(existente)
                        logger.info("Ya existe y es válido: %s", existente.name)
                        return _resumen("existente", existente, validacion, recurso)
                    except ErrorValidacionArchivo:
                        logger.warning("%s existe pero no es válido; se descargará de nuevo.", existente.name)

            temporal = fuente.carpeta / f"{base}.part"
            descargado = 0
            with open(temporal, "wb") as salida:
                for bloque in respuesta.iter_content(TAMANO_BLOQUE):
                    descargado += len(bloque)
                    if descargado > TAMANO_MAXIMO_BYTES:
                        raise ErrorDescarga("El archivo supera el tamaño máximo permitido.")
                    salida.write(bloque)

        if not extension:
            extension = detectar_extension(temporal)
            if not extension:
                raise ErrorDescarga("No se pudo determinar el tipo de archivo descargado.")

        validacion = validar_archivo(temporal, extension=extension)
        destino = fuente.carpeta / f"{base}{extension}"
        os.replace(temporal, destino)
        temporal = None
        logger.info("Descargado: %s (%d bytes)", destino.name, validacion["tamano_bytes"])
        return _resumen("descargado", destino, validacion, recurso)

    except requests.exceptions.RequestException as exc:
        raise ErrorDescarga(f"Error de red al descargar {url}: {exc}") from exc
    except ErrorValidacionArchivo as exc:
        raise ErrorDescarga(f"Archivo inválido desde {url}: {exc}") from exc
    finally:
        if temporal is not None and temporal.exists():
            temporal.unlink()
        if sesion_propia:
            sesion.close()


def descargar_recursos(
    recursos: list[dict],
    sesion: requests.Session | None = None,
    forzar: bool = False,
) -> list[dict]:
    """
    Descarga varios recursos. Un fallo no detiene el resto: se devuelve un
    resultado por recurso, con estado 'descargado', 'existente' o 'error'.
    """
    sesion_propia = sesion is None
    sesion = sesion or crear_sesion()
    resultados = []
    try:
        for recurso in recursos:
            try:
                resultados.append(descargar_recurso(recurso, sesion, forzar))
            except ErrorDescarga as exc:
                logger.error("%s", exc)
                resultados.append(
                    {
                        "estado": "error",
                        "fuente": recurso["fuente"],
                        "periodo": recurso.get("periodo"),
                        "url": recurso["url"],
                        "error": str(exc),
                    }
                )
    finally:
        if sesion_propia:
            sesion.close()
    return resultados