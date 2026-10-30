"""
Endpoint: POST /api/sbs/descargar/
Body JSON: {"recursos": ["clave_simple", {"clave": "boletin_informativo_mensual", "anio": 2019, "mes": 3}]}

Controles de seguridad:
  - Solo POST, protegido por CSRF (no se exime) y sesión autenticada de staff.
  - Solo peticiones locales (REMOTE_ADDR): este endpoint mueve el cursor y abre
    ventanas EN LA MÁQUINA DEL SERVIDOR, así que jamás debe ser invocable desde fuera.
    (No se confía en X-Forwarded-For.)
  - Cuerpo limitado, esquema validado, claves de catálogo cerrado, máx. 3 por llamada.
  - Errores genéricos al cliente; el detalle queda sólo en el log del servidor.
  - Respuestas sin caché y sin rutas absolutas del sistema de archivos.
"""
import json
import logging
import re

from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from descarga_macros.navegador import ErrorDescargaSBS, descargar_recurso

log = logging.getLogger(__name__)

MAX_BODY = 1024
MAX_RECURSOS = 3
CLAVE_RE = re.compile(r"^[a-z0-9_]{1,50}$")
IPS_LOCALES = {"127.0.0.1", "::1"}


def _normalizar(item):
    """Acepta "clave" o {"clave", "anio", "mes"}; cualquier otra forma/campo se rechaza."""
    if isinstance(item, str):
        clave, anio, mes = item, None, None
    elif isinstance(item, dict) and set(item) <= {"clave", "anio", "mes"}:
        clave, anio, mes = item.get("clave"), item.get("anio"), item.get("mes")
    else:
        raise ValueError
    if not (isinstance(clave, str) and CLAVE_RE.fullmatch(clave)):
        raise ValueError
    for n in (anio, mes):   # enteros estrictos (bool es subclase de int: se descarta)
        if n is not None and type(n) is not int:
            raise ValueError
    return clave, anio, mes


def _json(datos: dict, status: int = 200) -> JsonResponse:
    resp = JsonResponse(datos, status=status)
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


@never_cache
@csrf_protect
@require_POST
def descargar_sbs(request):
    if request.META.get("REMOTE_ADDR") not in IPS_LOCALES:
        log.warning("Intento de uso remoto del endpoint de descarga SBS.")
        return _json({"error": "prohibido"}, 403)

    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.is_staff):
        return _json({"error": "no_autorizado"}, 403)

    if len(request.body) > MAX_BODY:
        return _json({"error": "cuerpo_demasiado_grande"}, 413)
    try:
        datos = json.loads(request.body.decode("utf-8"))
        recursos = datos["recursos"]
        if not isinstance(recursos, list) or not 1 <= len(recursos) <= MAX_RECURSOS:
            raise ValueError
        pedidos = list(dict.fromkeys(_normalizar(r) for r in recursos))   # sin duplicados
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return _json({"error": "solicitud_invalida"}, 400)

    resultados, status = [], 200
    for clave, anio, mes in pedidos:
        try:
            resultados.append({"ok": True, **descargar_recurso(clave, anio, mes)})
        except ErrorDescargaSBS as exc:
            log.warning("Descarga SBS fallida: recurso=%s codigo=%s", clave, exc.codigo)
            resultados.append({"ok": False, "clave": clave, "anio": anio, "mes": mes,
                               "error": exc.codigo, "detalle": exc.mensaje_publico})
            status = exc.http_status
            break   # si falla uno, no se sigue controlando el cursor
    return _json({"resultados": resultados}, status)