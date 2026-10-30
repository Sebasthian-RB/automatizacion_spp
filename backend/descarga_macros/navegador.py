"""
Descarga de archivos de la SBS usando el navegador REAL instalado (Chrome/Edge)
y control del cursor, únicamente mientras dura la llamada.

Garantías de diseño
-------------------
* Sin persistencia de sesión: el navegador se abre en modo privado (--incognito /
  --inprivate) con un perfil TEMPORAL que se elimina al terminar. No quedan
  cookies, historial, caché, tokens ni credenciales.
* Control acotado: un único candado global (un solo proceso controla el cursor a
  la vez), tiempo máximo total, pyautogui FAILSAFE (mover el mouse a la esquina
  superior izquierda aborta), y comprobación de que la ventana activa sigue
  siendo el navegador antes de cada acción.
* Superficie de entrada mínima: sólo claves de un catálogo cerrado; URL validada
  contra una lista blanca (https, host exacto, sin credenciales, sin puertos).
* Archivo descargado validado (extensión, tamaño, firma "magic bytes") y guardado
  con nombre generado por nosotros (nunca el nombre remoto => sin path traversal).
* Al terminar (éxito o error) se cierra el navegador y se borra el perfil temporal.

Requisitos: Windows con sesión de escritorio activa (el servidor debe correr en la
sesión del usuario, p. ej. `manage.py runserver`, no como servicio).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings

from descarga_macros.recursos import RECURSOS_SBS

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #
HOSTS_PERMITIDOS = frozenset({"www.sbs.gob.pe", "sbs.gob.pe"})
NAVEGADORES_PERMITIDOS = frozenset({"chrome.exe", "msedge.exe"})
CLAVE_RE = re.compile(r"^[a-z0-9_]{1,50}$")
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "setiembre", "octubre", "noviembre", "diciembre")   # = nombres de las capturas mes_*.png
ANIO_MIN = 1996   # el Boletín Informativo Mensual de la SBS empieza en 1996
MARCAS_PRIVADO = ("InPrivate", "Incógnito", "Incognito")
TITULOS_OK = ("SBS", "Superintendencia", "Chrome", "Edge", "InPrivate", "Incógnito", "Incognito",
              "Guardar como", "Save As")   # los dos últimos: diálogo de guardado del navegador
IMAGEN_RE = re.compile(r"^[A-Za-z0-9_\-]{1,60}\.png$")
REFERENCIAS_DIR = Path(__file__).resolve().parent / "referencias_ui"
EXT_PARCIALES = {".crdownload", ".tmp", ".part"}
FIRMAS = {  # "magic bytes" por extensión; None = se valida como texto
    ".pdf": (b"%PDF",),
    ".xlsx": (b"PK\x03\x04",),
    ".zip": (b"PK\x03\x04",),
    ".rar": (b"Rar!\x1a\x07",),
    ".xls": (b"\xD0\xCF\x11\xE0",),
    ".csv": None,
}

_LOCK = threading.Lock()          # un solo control de cursor a la vez (por proceso)
_ultima_ejecucion = 0.0


def _cfg(nombre: str, defecto):
    return getattr(settings, nombre, defecto)


# --------------------------------------------------------------------------- #
# Errores (mensaje_publico es lo único que se devuelve al cliente)
# --------------------------------------------------------------------------- #
class ErrorDescargaSBS(Exception):
    codigo = "error_interno"
    mensaje_publico = "No se pudo completar la descarga."
    http_status = 500

    def __init__(self, detalle: str = ""):
        super().__init__(detalle)
        self.detalle = detalle   # sólo diagnóstico local; la API NUNCA lo devuelve al cliente


class RecursoNoPermitido(ErrorDescargaSBS):
    codigo, mensaje_publico, http_status = "recurso_no_permitido", "Recurso no permitido.", 400


class UrlNoPermitida(ErrorDescargaSBS):
    codigo, mensaje_publico, http_status = "url_no_permitida", "Configuración de URL no permitida.", 500


class SistemaOcupado(ErrorDescargaSBS):
    codigo, mensaje_publico, http_status = "ocupado", "Ya hay una descarga en curso.", 409


class EnfriamientoActivo(ErrorDescargaSBS):
    codigo, mensaje_publico, http_status = "demasiado_pronto", "Espere antes de volver a ejecutar.", 429


class NavegadorNoEncontrado(ErrorDescargaSBS):
    codigo, mensaje_publico = "navegador_no_disponible", "Navegador no disponible en el servidor."


class ControlInterrumpido(ErrorDescargaSBS):
    codigo, mensaje_publico = "control_interrumpido", "El control del cursor fue interrumpido."


class ElementoNoEncontrado(ErrorDescargaSBS):
    codigo, mensaje_publico, http_status = "elemento_no_encontrado", "No se encontró un elemento en pantalla.", 502


class DescargaNoCompletada(ErrorDescargaSBS):
    codigo, mensaje_publico, http_status = "descarga_no_completada", "La descarga no se completó a tiempo.", 504


class ArchivoInvalido(ErrorDescargaSBS):
    codigo, mensaje_publico, http_status = "archivo_invalido", "El archivo descargado no es válido.", 502


# --------------------------------------------------------------------------- #
# Validaciones de entrada
# --------------------------------------------------------------------------- #
def validar_clave(clave) -> str:
    if not isinstance(clave, str) or not CLAVE_RE.fullmatch(clave) or clave not in RECURSOS_SBS:
        raise RecursoNoPermitido()
    return clave


def validar_periodo(recurso: dict, anio, mes):
    """Año/mes sólo se aceptan si el recurso es "periodo": True; enteros estrictos y en rango."""
    if not recurso.get("periodo"):
        if anio is not None or mes is not None:
            raise RecursoNoPermitido()
        return None, None
    anio_max = datetime.now(timezone.utc).year
    if (type(anio) is not int or type(mes) is not int          # `type is int` rechaza bool/str/float
            or not ANIO_MIN <= anio <= anio_max or not 1 <= mes <= 12):
        raise RecursoNoPermitido()
    return anio, mes


def _resolver_pasos(pasos: list[dict], anio, mes) -> list[dict]:
    """
    Sustituye {anio}/{mes} en los nombres de imagen (valores ya validados) y descarta los pasos
    cuyo "solo_si_anio": {"min": a, "max": b} no cubre el año pedido.
    """
    if anio is None:
        return [{k: v for k, v in p.items() if k != "solo_si_anio"} for p in pasos]
    reemplazos = {"{anio}": str(anio), "{mes}": MESES[mes - 1]}
    resueltos = []
    for paso in pasos:
        p = dict(paso)
        cond = p.pop("solo_si_anio", None)
        if cond is not None and not (cond.get("min", ANIO_MIN) <= anio <= cond.get("max", 9999)):
            continue
        for campo in ("imagen", "debajo_de"):
            if isinstance(p.get(campo), str):
                for k, v in reemplazos.items():
                    p[campo] = p[campo].replace(k, v)
        resueltos.append(p)
    return resueltos


def validar_url(url) -> str:
    """Lista blanca estricta: https + host exacto + sin credenciales + puerto 443."""
    try:
        if not isinstance(url, str) or len(url) > 2048 or re.search(r"[\s\x00-\x1f]", url):
            raise ValueError
        p = urlparse(url)
        host = (p.hostname or "").lower()
        host.encode("ascii")  # rechaza homógrafos / IDN
        if (p.scheme != "https" or p.username or p.password
                or p.port not in (None, 443) or host not in HOSTS_PERMITIDOS):
            raise ValueError
    except (ValueError, UnicodeEncodeError):
        raise UrlNoPermitida()
    return url


# --------------------------------------------------------------------------- #
# Navegador real, perfil temporal y modo privado
# --------------------------------------------------------------------------- #
def _ruta_navegador() -> str:
    local = os.environ.get("LOCALAPPDATA", "")
    candidatos = [
        _cfg("SBS_NAVEGADOR_EXE", None),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(local, r"Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidatos:
        if c and os.path.isfile(c) and os.path.basename(c).lower() in NAVEGADORES_PERMITIDOS:
            return c
    raise NavegadorNoEncontrado()


def _preparar_perfil(raiz: Path) -> tuple[Path, Path]:
    perfil, descargas = raiz / "perfil", raiz / "descargas"
    (perfil / "Default").mkdir(parents=True)
    descargas.mkdir()
    prefs = {
        "download": {"default_directory": str(descargas), "prompt_for_download": False,
                     "directory_upgrade": True},
        "savefile": {"default_directory": str(descargas)},
        "plugins": {"always_open_pdf_externally": True},   # PDF se descarga, no se previsualiza
        "profile": {"password_manager_enabled": False},
        "credentials_enable_service": False,
        "safebrowsing": {"enabled": True},
    }
    (perfil / "Default" / "Preferences").write_text(json.dumps(prefs), encoding="utf-8")
    return perfil, descargas


def _lanzar_navegador(exe: str, perfil: Path, url: str) -> subprocess.Popen:
    privado = "--inprivate" if os.path.basename(exe).lower() == "msedge.exe" else "--incognito"
    cmd = [exe, f"--user-data-dir={perfil}", privado, "--no-first-run",
           "--no-default-browser-check", "--disable-extensions", "--disable-sync",
           "--start-maximized", "--new-window", url]
    # shell=False y lista de argumentos => sin inyección de comandos
    return subprocess.Popen(cmd, shell=False, stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _cerrar_navegador(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=10, check=False)
        else:
            proc.terminate()
        proc.wait(timeout=10)
    except Exception:  # noqa: BLE001
        log.warning("No se pudo cerrar limpiamente el navegador.")


def _borrar_temporal(raiz: Path) -> None:
    for _ in range(6):  # Windows tarda en liberar los archivos
        shutil.rmtree(raiz, ignore_errors=True)
        if not raiz.exists():
            return
        time.sleep(0.5)
    log.warning("No se pudo borrar el perfil temporal del navegador.")


# --------------------------------------------------------------------------- #
# Control del cursor
# --------------------------------------------------------------------------- #
def _ventana_ok(pyautogui) -> None:
    """Aborta si la ventana activa ya no es el navegador (usuario interfirió)."""
    obtener = getattr(pyautogui, "getActiveWindowTitle", None)
    titulo = obtener() if obtener else None
    if titulo is not None and not any(h in titulo for h in TITULOS_OK):
        raise ControlInterrumpido(f"la ventana activa no es el navegador: {titulo!r}")


def _enfocar_navegador(pyautogui, limite: float) -> None:
    """
    Tras lanzar el navegador, espera a que su ventana privada tome el foco (si no, se lo pide)
    ANTES de tocar nada. Al arrancar, la ventana activa suele seguir siendo el editor/terminal.
    """
    obtener = getattr(pyautogui, "getActiveWindowTitle", None)
    if obtener is None:
        return   # sin API de ventanas no se puede comprobar
    encontrar = getattr(pyautogui, "getWindowsWithTitle", None)
    fin = min(limite, time.monotonic() + 25)
    titulo = None
    while time.monotonic() < fin:
        titulo = obtener()
        if titulo is None or any(m in titulo for m in MARCAS_PRIVADO):
            return
        if encontrar:
            for marca in MARCAS_PRIVADO:
                try:
                    ventanas = encontrar(marca)
                    if ventanas:
                        ventanas[0].activate()
                        break
                except Exception:  # activate() a veces lanza error aunque funcione
                    pass
        time.sleep(0.7)
    if titulo is not None and any(h in titulo for h in TITULOS_OK):
        return   # es un navegador aunque el título no muestre la marca de modo privado
    raise ControlInterrumpido(f"el navegador no tomó el foco; ventana activa: {titulo!r}")


def _ruta_imagen(nombre) -> Path:
    if not isinstance(nombre, str) or not IMAGEN_RE.fullmatch(nombre):
        raise ElementoNoEncontrado()
    ruta = (REFERENCIAS_DIR / nombre).resolve()
    if ruta.parent != REFERENCIAS_DIR.resolve() or not ruta.is_file():
        raise ElementoNoEncontrado()
    return ruta


def _localizar(pyautogui, ruta: Path, confianza: float, region=None):
    try:
        return pyautogui.locateCenterOnScreen(
            str(ruta), confidence=max(0.7, min(float(confianza), 0.99)), region=region)
    except Exception:  # ImageNotFoundException según versión
        return None


def _buscar_imagen(pyautogui, nombre: str, timeout: float, confianza: float,
                   ancla: str | None = None, scroll: int = 0):
    """
    Busca una captura en pantalla.
      ancla : nombre de otra captura (p. ej. el rótulo del año). Si se indica, sólo se acepta
              la coincidencia que esté POR DEBAJO de ella (distingue el "Enero" de cada año).
              El ancla se vuelve a localizar en cada reintento, así que sigue válida tras scroll.
      scroll: si no la encuentra, desplaza la página y reintenta (años lejanos / meses fuera de vista).
    """
    ruta = _ruta_imagen(nombre)
    ruta_ancla = _ruta_imagen(ancla) if ancla else None
    ancho, alto = pyautogui.size()
    scroll = max(-1000, min(int(scroll), 1000))
    fin = time.monotonic() + min(float(timeout), 90)
    while time.monotonic() < fin:
        buscar, region = True, None
        if ruta_ancla is not None:
            a = _localizar(pyautogui, ruta_ancla, 0.8)
            if a is None:
                buscar = False          # el ancla no está a la vista todavía
            else:
                top = max(0, min(int(a.y) + 10, alto - 2))
                region = (0, top, ancho, alto - top)
        if buscar:
            pos = _localizar(pyautogui, ruta, confianza, region)
            if pos:
                return pos
        if scroll:
            _ventana_ok(pyautogui)
            pyautogui.scroll(scroll)
        time.sleep(0.5)
    raise ElementoNoEncontrado()


def _guardar_como(pyautogui, descargas: Path, paso: dict, limite: float) -> None:
    """Ctrl+S -> escribe una ruta NUESTRA (carpeta temporal) en el diálogo -> Enter."""
    ext = str(paso.get("extension", "")).lower()
    if ext not in FIRMAS:
        raise ControlInterrumpido()
    ruta = descargas / f"pagina{ext}"
    if not str(ruta).isascii():      # pyautogui.write no escribe bien caracteres no ASCII
        raise ControlInterrumpido()
    obtener = getattr(pyautogui, "getActiveWindowTitle", None)
    if obtener is None:
        raise ControlInterrumpido()
    pyautogui.hotkey("ctrl", "s")
    fin = min(limite, time.monotonic() + 15)
    while time.monotonic() < fin:
        titulo = obtener() or ""
        if "Guardar como" in titulo or "Save As" in titulo:
            break
        time.sleep(0.3)
    else:
        raise ControlInterrumpido()
    time.sleep(0.5)
    pyautogui.write(str(ruta), interval=0.02)
    pyautogui.press("enter")


def _ejecutar_pasos(pasos: list[dict], limite: float, descargas: Path) -> None:
    import pyautogui  # import tardío: falla si no hay escritorio

    pyautogui.FAILSAFE = True   # esquina superior izquierda = abortar
    pyautogui.PAUSE = 0.3
    ancho, alto = pyautogui.size()
    _enfocar_navegador(pyautogui, limite)

    for paso in pasos:
        if time.monotonic() > limite:
            raise ControlInterrumpido("se agotó el tiempo máximo de control (timeout_total)")
        _ventana_ok(pyautogui)
        accion = paso.get("accion")
        try:
            if accion == "esperar":
                time.sleep(max(0.0, min(float(paso["segundos"]), 30.0)))
            elif accion == "click_imagen":
                pos = _buscar_imagen(pyautogui, paso["imagen"], paso.get("timeout", 15),
                                     paso.get("confianza", 0.85),
                                     paso.get("debajo_de"), paso.get("scroll", 0))
                # dx/dy: desplazamiento desde la imagen (p. ej. clic en un botón bajo el rótulo "2025")
                dx = max(-1500, min(int(paso.get("dx", 0)), 1500))
                dy = max(-1500, min(int(paso.get("dy", 0)), 1500))
                x = max(0, min(int(pos.x) + dx, ancho - 1))
                y = max(0, min(int(pos.y) + dy, alto - 1))
                pyautogui.moveTo(x, y, duration=0.6, tween=pyautogui.easeInOutQuad)
                if paso.get("alt"):
                    # Alt+clic: Chrome/Edge DESCARGAN el destino del enlace en vez de abrirlo
                    pyautogui.keyDown("alt")
                    try:
                        pyautogui.click()
                    finally:
                        pyautogui.keyUp("alt")
                else:
                    pyautogui.click()
            elif accion == "click_relativo":
                fx, fy = float(paso["x"]), float(paso["y"])
                if not (0 < fx < 1 and 0 < fy < 1):
                    raise ValueError
                pyautogui.moveTo(int(ancho * fx), int(alto * fy), duration=0.6,
                                 tween=pyautogui.easeInOutQuad)
                pyautogui.click()
            elif accion == "mover_relativo":
                fx, fy = float(paso["x"]), float(paso["y"])
                if not (0 < fx < 1 and 0 < fy < 1):
                    raise ValueError
                pyautogui.moveTo(int(ancho * fx), int(alto * fy), duration=0.4,
                                 tween=pyautogui.easeInOutQuad)
            elif accion == "scroll":
                pyautogui.scroll(max(-2000, min(int(paso["cantidad"]), 2000)))
            elif accion == "guardar_como":
                _guardar_como(pyautogui, descargas, paso, limite)
            else:
                raise ValueError
        except pyautogui.FailSafeException:
            raise ControlInterrumpido("failsafe: el mouse llegó a la esquina superior izquierda")
        except ErrorDescargaSBS:
            raise
        except (KeyError, ValueError, TypeError) as exc:
            raise ControlInterrumpido(f"paso inválido {accion!r}: {exc!r}")


# --------------------------------------------------------------------------- #
# Espera y validación del archivo
# --------------------------------------------------------------------------- #
def _esperar_descarga(carpeta: Path, extensiones: set[str], timeout: float, max_bytes: int) -> Path:
    fin = time.monotonic() + timeout
    while time.monotonic() < fin:
        archivos = [f for f in carpeta.iterdir() if f.is_file()]
        for f in archivos:  # corta si un parcial supera el tamaño máximo
            if f.stat().st_size > max_bytes:
                raise ArchivoInvalido()
        parciales = any(f.suffix.lower() in EXT_PARCIALES for f in archivos)
        listos = [f for f in archivos if f.suffix.lower() in extensiones]
        if listos and not parciales:
            f = listos[0]
            t1 = f.stat().st_size
            time.sleep(1.0)
            if t1 > 0 and t1 == f.stat().st_size:   # tamaño estable => terminó
                return f
        time.sleep(0.5)
    raise DescargaNoCompletada()


def _validar_archivo(ruta: Path, extensiones: set[str], max_bytes: int) -> str:
    ext = ruta.suffix.lower()
    if ext not in extensiones or ext not in FIRMAS:
        raise ArchivoInvalido()
    tam = ruta.stat().st_size
    if tam == 0 or tam > max_bytes:
        raise ArchivoInvalido()
    with ruta.open("rb") as fh:
        cabecera = fh.read(4096)
    firmas = FIRMAS[ext]
    if firmas is None:  # CSV: texto sin bytes nulos
        if b"\x00" in cabecera:
            raise ArchivoInvalido()
    elif not any(cabecera.startswith(s) for s in firmas):
        raise ArchivoInvalido()
    return ext


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def _mover_a_destino(origen: Path, prefijo: str, ext: str) -> Path:
    destino_dir = Path(_cfg("SBS_DESCARGAS_DIR", Path(settings.BASE_DIR) / "datos_descargados" / "sbs"))
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino_dir = destino_dir.resolve()
    marca = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final = (destino_dir / f"{prefijo}_{marca}_{uuid.uuid4().hex[:8]}{ext}").resolve()
    if final.parent != destino_dir:  # defensa extra contra path traversal
        raise ArchivoInvalido()
    shutil.move(str(origen), str(final))
    return final


# --------------------------------------------------------------------------- #
# API pública del servicio
# --------------------------------------------------------------------------- #
def descargar_recurso(clave: str, anio: int | None = None, mes: int | None = None) -> dict:
    """
    Abre el navegador real, mueve el cursor según el catálogo, espera la descarga,
    valida el archivo y lo guarda. Devuelve sólo metadatos (sin rutas absolutas).
    """
    global _ultima_ejecucion
    clave = validar_clave(clave)
    recurso = RECURSOS_SBS[clave]
    anio, mes = validar_periodo(recurso, anio, mes)
    pasos = _resolver_pasos(recurso["pasos"], anio, mes)
    prefijo = f"{clave}_{anio}{mes:02d}" if anio else clave
    url = validar_url(recurso["url"])
    extensiones = {e.lower() for e in recurso["extensiones"]}
    max_bytes = int(_cfg("SBS_MAX_BYTES", 50 * 1024 * 1024))

    if not _LOCK.acquire(blocking=False):
        raise SistemaOcupado()
    raiz, proc = None, None
    try:
        if time.monotonic() - _ultima_ejecucion < int(_cfg("SBS_COOLDOWN_SEGUNDOS", 30)):
            raise EnfriamientoActivo()
        _ultima_ejecucion = time.monotonic()

        exe = _ruta_navegador()
        raiz = Path(tempfile.mkdtemp(prefix="sbs_"))   # carpeta privada del usuario
        perfil, descargas = _preparar_perfil(raiz)
        limite = time.monotonic() + int(recurso.get("timeout_total", 120))

        log.info("Inicio de descarga SBS: recurso=%s periodo=%s-%s", clave, anio, mes)   # sin URL, sin cookies
        proc = _lanzar_navegador(exe, perfil, url)
        _ejecutar_pasos(pasos, limite, descargas)

        bruto = _esperar_descarga(descargas, extensiones,
                                  int(recurso.get("timeout_descarga", 60)), max_bytes)
        ext = _validar_archivo(bruto, extensiones, max_bytes)
        digest = _sha256(bruto)
        tam = bruto.stat().st_size
        final = _mover_a_destino(bruto, prefijo, ext)

        log.info("Descarga SBS completada: recurso=%s bytes=%s", clave, tam)
        return {"clave": clave, "anio": anio, "mes": mes, "archivo": final.name,
                "extension": ext, "bytes": tam, "sha256": digest}
    except ErrorDescargaSBS:
        raise
    except Exception:  # noqa: BLE001 - nada interno se filtra al cliente
        log.exception("Fallo inesperado en descarga SBS: recurso=%s", clave)
        raise ErrorDescargaSBS()
    finally:
        _cerrar_navegador(proc)      # el cursor/navegador se liberan SIEMPRE
        if raiz is not None:
            _borrar_temporal(raiz)   # no queda ni cookie ni caché ni historial
        _LOCK.release()