"""
Endpoint: POST /api/sbs/descargar/
Body JSON:
  {"recursos": [ "clave"
               | {"clave": "x", "anio": 2025, "mes": 3}
               | {"clave": "x", "periodos": [{"anio": 2025, "mes": 3}, {"anio": 2025, "mes": 4}]} ],
   "forzar": false}

Por defecto OMITE lo ya descargado e íntegro ("ya_descargado"); "forzar": true lo vuelve a bajar.
Para sincronizaciones grandes (muchos años) usa el script sincronizar_sbs.py, no la API.

Controles de seguridad:
  - Solo POST, protegido por CSRF (no se exime) y sesión autenticada de staff.
  - Solo peticiones locales (REMOTE_ADDR): este endpoint mueve el cursor y abre
    ventanas EN LA MÁQUINA DEL SERVIDOR, así que jamás debe ser invocable desde fuera.
    (No se confía en X-Forwarded-For.)
  - Cuerpo limitado, esquema validado, claves de catálogo cerrado, máx. 3 recursos y 24 períodos por llamada.
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

from descarga_macros.navegador import ErrorDescargaSBS, descargar_lote

log = logging.getLogger(__name__)

MAX_BODY = 4096
MAX_PERIODOS = 24
MAX_RECURSOS = 3
CLAVE_RE = re.compile(r"^[a-z0-9_]{1,50}$")
IPS_LOCALES = {"127.0.0.1", "::1"}


def _entero(n):
    return type(n) is int      # rechaza bool, str, float, None


def _normalizar(item):
    """Devuelve (clave, periodos|None). Acepta "clave", {"clave","anio","mes"} o {"clave","periodos":[...]}."""
    if isinstance(item, str):
        clave, periodos = item, None
    elif isinstance(item, dict) and set(item) <= {"clave", "anio", "mes", "periodos"}:
        clave = item.get("clave")
        if "periodos" in item:
            if "anio" in item or "mes" in item:
                raise ValueError
            crudos = item["periodos"]
            if not isinstance(crudos, list) or not 1 <= len(crudos) <= MAX_PERIODOS:
                raise ValueError
            periodos = []
            for q in crudos:
                if not (isinstance(q, dict) and set(q) == {"anio", "mes"}):
                    raise ValueError
                periodos.append((q["anio"], q["mes"]))
        elif "anio" in item or "mes" in item:
            periodos = [(item.get("anio"), item.get("mes"))]
        else:
            periodos = None
    else:
        raise ValueError
    if not (isinstance(clave, str) and CLAVE_RE.fullmatch(clave)):
        raise ValueError
    if periodos is not None:
        if not all(_entero(n) for q in periodos for n in q):
            raise ValueError
        periodos = tuple(periodos)
    return clave, periodos


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
        forzar = datos.get("forzar", False)
        if (not isinstance(recursos, list) or not 1 <= len(recursos) <= MAX_RECURSOS
                or type(forzar) is not bool):
            raise ValueError
        pedidos = list(dict.fromkeys(_normalizar(r) for r in recursos))   # sin duplicados
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, AttributeError):
        return _json({"error": "solicitud_invalida"}, 400)

    resultados, status = [], 200
    for clave, periodos in pedidos:
        try:
            lote = descargar_lote(clave, list(periodos) if periodos else None, forzar=forzar)
        except ErrorDescargaSBS as exc:
            log.warning("Descarga SBS fallida: recurso=%s codigo=%s", clave, exc.codigo)
            resultados.append({"clave": clave, "estado": "error", "error": exc.codigo,
                               "mensaje": exc.mensaje_publico})
            status = exc.http_status
            break   # no se sigue controlando el cursor
        resultados.extend(lote)
        if any(r.get("abortado") for r in lote):
            break
    ok = all(r.get("estado") in ("descargado", "ya_descargado", "no_disponible") for r in resultados)
    return _json({"ok": ok, "resultados": resultados}, status)