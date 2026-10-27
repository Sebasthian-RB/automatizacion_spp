
import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone

from fuentes.models import FuenteDatos, RecursoFuente


FORMATOS_ADMITIDOS = {
    ".xlsx",
    ".xls",
    ".csv",
    ".pdf",
    ".zip",
}

DOMINIOS_ADMITIDOS = {
    "sbs.gob.pe",
    "www.sbs.gob.pe",
    "aiosfp.org",
    "www.aiosfp.org",
}


def obtener_sesion():
    sesion = requests.Session()
    sesion.headers.update({
        "User-Agent": "AutomatizacionEstadisticasSPP/1.0",
    })
    return sesion


def obtener_directorio_bruto(institucion):
    directorio = (
        Path(settings.BASE_DIR)
        / "data"
        / "raw"
        / institucion
    )
    directorio.mkdir(parents=True, exist_ok=True)
    return directorio


def dominio_permitido(url):
    dominio = (urlparse(url).hostname or "").lower()
    return any(
        dominio == permitido
        or dominio.endswith("." + permitido)
        for permitido in DOMINIOS_ADMITIDOS
    )


def obtener_extension(url):
    ruta = unquote(urlparse(url).path).lower()
    return Path(ruta).suffix


def crear_nombre_seguro(nombre):
    nombre = Path(unquote(nombre)).name
    nombre = re.sub(r"[^a-zA-Z0-9._-]", "_", nombre)
    return nombre[:180] or "recurso"


def guardar_contenido(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(contenido)


def descubrir_y_descargar_fuente(fuente):
    sesion = obtener_sesion()
    respuesta = sesion.get(fuente.url_publicacion, timeout=(10, 60))
    respuesta.raise_for_status()

    contenido_html = respuesta.content
    fecha_ejecucion = datetime.now().strftime("%Y%m%d_%H%M%S")

    directorio = obtener_directorio_bruto(fuente.institucion)
    nombre_base = crear_nombre_seguro(fuente.nombre.replace(" ", "_"))

    ruta_html = directorio / (
        f"{nombre_base}_{fecha_ejecucion}.html"
    )
    guardar_contenido(ruta_html, contenido_html)

    soup = BeautifulSoup(contenido_html, "html.parser")
    recursos = []

    for enlace in soup.find_all("a", href=True):
        url_recurso = urljoin(respuesta.url, enlace["href"].strip())
        extension = obtener_extension(url_recurso)

        if not dominio_permitido(url_recurso):
            continue

        if extension not in FORMATOS_ADMITIDOS:
            continue

        titulo = enlace.get_text(" ", strip=True)
        if not titulo:
            titulo = Path(
                unquote(urlparse(url_recurso).path)
            ).name

        recurso, _ = RecursoFuente.objects.update_or_create(
            url=url_recurso,
            defaults={
                "fuente": fuente,
                "titulo": titulo[:500],
                "formato": extension.lstrip(".").upper(),
                "estado": RecursoFuente.Estado.DETECTADO,
                "detalle_error": "",
            },
        )
        recursos.append(recurso)

    resultados = []

    for recurso in recursos:
        try:
            respuesta_archivo = sesion.get(
                recurso.url,
                timeout=(10, 120),
            )
            respuesta_archivo.raise_for_status()

            contenido = respuesta_archivo.content
            if not contenido:
                raise ValueError("El recurso descargado está vacío.")

            hash_contenido = hashlib.sha256(contenido).hexdigest()
            extension = obtener_extension(recurso.url)
            nombre_archivo = crear_nombre_seguro(
                Path(unquote(urlparse(recurso.url).path)).name
            )

            if not Path(nombre_archivo).suffix:
                nombre_archivo += extension

            directorio_recurso = (
                directorio
                / "archivos"
                / hash_contenido[:2]
            )
            ruta_archivo = (
                directorio_recurso
                / f"{hash_contenido[:12]}_{nombre_archivo}"
            )

            if not ruta_archivo.exists():
                guardar_contenido(ruta_archivo, contenido)

            recurso.ruta_archivo = str(ruta_archivo)
            recurso.sha256 = hash_contenido
            recurso.descargado_en = timezone.now()
            recurso.estado = RecursoFuente.Estado.DESCARGADO
            recurso.detalle_error = ""
            recurso.save()

            resultados.append({
                "recurso": recurso.titulo,
                "estado": "DESCARGADO",
                "ruta": str(ruta_archivo),
            })

        except (requests.RequestException, OSError, ValueError) as error:
            recurso.estado = RecursoFuente.Estado.ERROR
            recurso.detalle_error = str(error)[:4000]
            recurso.save(
                update_fields=["estado", "detalle_error"]
            )

            resultados.append({
                "recurso": recurso.titulo,
                "estado": "ERROR",
                "detalle": str(error),
            })

    return {
        "fuente": fuente.nombre,
        "pagina_guardada": str(ruta_html),
        "recursos_detectados": len(recursos),
        "resultados": resultados,
    }
