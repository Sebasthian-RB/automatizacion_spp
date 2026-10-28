"""
Validación de archivos descargados.

Comprueba, en orden: existencia y tamaño, extensión permitida, que el
contenido corresponda a la extensión (firma del archivo) y que el archivo
no esté corrupto. Así se detectan casos típicos como una página HTML de error
guardada con extensión .xlsx.
"""
import logging
import zipfile
from pathlib import Path

from fuentes.configuracion import (
    EXTENSIONES_PERMITIDAS,
    TAMANO_MAXIMO_BYTES,
    TAMANO_MINIMO_BYTES,
)

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

logger = logging.getLogger(__name__)

_FIRMA_ZIP = b"PK\x03\x04"
_FIRMA_OLE = b"\xd0\xcf\x11\xe0"  # .xls antiguo
_FIRMA_PDF = b"%PDF"

_FIRMAS = {
    ".xlsx": (_FIRMA_ZIP,),
    ".xlsm": (_FIRMA_ZIP,),
    ".zip": (_FIRMA_ZIP,),
    ".xls": (_FIRMA_OLE,),
    ".pdf": (_FIRMA_PDF,),
}


class ErrorValidacionArchivo(Exception):
    """El archivo descargado no es válido."""


def _leer_inicio(ruta: Path, n: int = 8) -> bytes:
    with open(ruta, "rb") as f:
        return f.read(n)


def detectar_extension(ruta: Path) -> str | None:
    """Deduce la extensión a partir del contenido. None si no la reconoce."""
    inicio = _leer_inicio(ruta)
    if inicio.startswith(_FIRMA_PDF):
        return ".pdf"
    if inicio.startswith(_FIRMA_OLE):
        return ".xls"
    if inicio.startswith(_FIRMA_ZIP):
        try:
            with zipfile.ZipFile(ruta) as z:
                nombres = z.namelist()
        except zipfile.BadZipFile:
            return None
        if "xl/workbook.xml" in nombres:
            return ".xlsm" if "xl/vbaProject.bin" in nombres else ".xlsx"
        return ".zip"
    return None


def _parece_html(ruta: Path) -> bool:
    inicio = _leer_inicio(ruta, 512).lstrip().lower()
    return inicio.startswith((b"<!doctype", b"<html", b"<head", b"<body", b"<?xml"))


def validar_archivo(ruta: Path | str, extension: str | None = None) -> dict:
    """
    Valida un archivo y devuelve un resumen:
        {"extension": ".xlsx", "tamano_bytes": 402168, "hojas": ["Hoja1", ...] | None}

    `extension` permite validar un archivo temporal (por ejemplo .part) como si
    tuviera esa extensión. Lanza ErrorValidacionArchivo si algo falla.
    """
    ruta = Path(ruta)
    extension = (extension or ruta.suffix).lower()

    if not ruta.is_file():
        raise ErrorValidacionArchivo(f"El archivo no existe: {ruta}")

    tamano = ruta.stat().st_size
    if tamano < TAMANO_MINIMO_BYTES:
        raise ErrorValidacionArchivo(
            f"Archivo demasiado pequeño ({tamano} bytes); probablemente vacío o un error."
        )
    if tamano > TAMANO_MAXIMO_BYTES:
        raise ErrorValidacionArchivo(f"Archivo demasiado grande ({tamano} bytes).")

    if extension not in EXTENSIONES_PERMITIDAS:
        raise ErrorValidacionArchivo(f"Extensión no permitida: '{extension}'.")

    if _parece_html(ruta):
        raise ErrorValidacionArchivo(
            "El contenido es HTML, no un archivo de datos (¿página de error o de inicio de sesión?)."
        )

    firmas = _FIRMAS.get(extension)
    if firmas and not _leer_inicio(ruta).startswith(firmas):
        raise ErrorValidacionArchivo(
            f"El contenido no corresponde a un archivo '{extension}'."
        )

    hojas = None
    if extension in (".xlsx", ".xlsm", ".zip"):
        try:
            with zipfile.ZipFile(ruta) as z:
                dañado = z.testzip()
        except zipfile.BadZipFile as exc:
            raise ErrorValidacionArchivo("El archivo está corrupto (zip inválido).") from exc
        if dañado:
            raise ErrorValidacionArchivo(f"Archivo corrupto: falla '{dañado}' dentro del zip.")

        if extension in (".xlsx", ".xlsm") and openpyxl is not None:
            try:
                # Se abre como archivo (no por ruta) porque openpyxl rechaza
                # rutas con extensión distinta de .xlsx, como el temporal .part.
                with open(ruta, "rb") as f:
                    libro = openpyxl.load_workbook(f, read_only=True)
                    try:
                        hojas = list(libro.sheetnames)
                    finally:
                        libro.close()
            except Exception as exc:  # openpyxl lanza varios tipos de error
                raise ErrorValidacionArchivo(f"Excel no se puede abrir: {exc}") from exc
            if not hojas:
                raise ErrorValidacionArchivo("El libro de Excel no tiene hojas.")

    elif extension == ".pdf":
        with open(ruta, "rb") as f:
            f.seek(max(0, tamano - 1024))
            if b"%%EOF" not in f.read():
                raise ErrorValidacionArchivo("PDF incompleto (falta el marcador de fin).")

    return {"extension": extension, "tamano_bytes": tamano, "hojas": hojas}