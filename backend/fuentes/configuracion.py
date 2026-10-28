"""
Configuración centralizada de las fuentes de datos.

Todo lo que dependa de URLs, tiempos de espera, reintentos o carpetas de
descarga debe leerse desde este módulo, nunca escribirse a mano en otro lado.
"""
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


# ---------------------------------------------------------------------------
# Parámetros generales de red
# ---------------------------------------------------------------------------
TIMEOUT_CONEXION = 10        # segundos para establecer la conexión
TIMEOUT_LECTURA = 60         # segundos para recibir la respuesta
TIMEOUT = (TIMEOUT_CONEXION, TIMEOUT_LECTURA)

MAX_REINTENTOS = 3
FACTOR_ESPERA_REINTENTOS = 2  # espera entre intentos: 2s, 4s, 8s...
CODIGOS_REINTENTABLES = (429, 500, 502, 503, 504)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-PE,es;q=0.9",
}

# Verificación de certificados SSL. Déjalo en True. Si algún sitio del Estado
# falla por su cadena de certificados, la solución correcta es indicar aquí la
# ruta a un bundle .pem; usa False solo como último recurso y solo en pruebas.
VERIFICAR_SSL = True
RUTA_CERTIFICADOS = None  # ejemplo: BASE_DIR / "certificados" / "sbs_bundle.pem"


# ---------------------------------------------------------------------------
# Carpetas de descarga
# ---------------------------------------------------------------------------
CARPETA_DESCARGAS = Path(settings.BASE_DIR) / "datos_descargados"

# Límites de validación de archivos descargados
TAMANO_MINIMO_BYTES = 1_024                 # menos de 1 KB: probablemente vacío o error
TAMANO_MAXIMO_BYTES = 200 * 1024 * 1024     # 200 MB
EXTENSIONES_PERMITIDAS = (".xls", ".xlsx", ".xlsm", ".csv", ".pdf", ".zip")


# ---------------------------------------------------------------------------
# Definición de las fuentes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FuenteConfig:
    codigo: str          # identificador interno, también nombre de la subcarpeta
    nombre: str          # nombre legible
    url: str             # página de origen donde se buscan los recursos
    dominio: str         # dominio base, para resolver enlaces relativos
    descripcion: str = ""

    @property
    def carpeta(self) -> Path:
        return CARPETA_DESCARGAS / self.codigo


SBS_AFP = FuenteConfig(
    codigo="sbs_afp",
    nombre="SBS - Estadísticas AFP",
    url="https://www.sbs.gob.pe/app/stats_net/stats/EstadisticaBoletinEstadistico.aspx?p=31",
    dominio="https://www.sbs.gob.pe",
    descripcion="Estadísticas vigentes del Sistema Privado de Pensiones.",
)

SBS_HISTORICO = FuenteConfig(
    codigo="sbs_historico",
    nombre="SBS - Histórico SPP",
    url="https://www.sbs.gob.pe/app/stats_net/stats/EstadisticaBoletinEstadisticoHist.aspx?p=36",
    dominio="https://www.sbs.gob.pe",
    descripcion="Series históricas del Sistema Privado de Pensiones.",
)

AIOS = FuenteConfig(
    codigo="aios",
    nombre="AIOS - Boletines",
    url="https://www.aiosfp.org/estadisticas/boletin-estadistico-aios.html",
    dominio="https://www.aiosfp.org",
    descripcion="Boletines estadísticos de AIOS.",
)

FUENTES = {f.codigo: f for f in (SBS_AFP, SBS_HISTORICO, AIOS)}


def obtener_fuente(codigo: str) -> FuenteConfig:
    """Devuelve la configuración de una fuente o lanza un error claro."""
    try:
        return FUENTES[codigo]
    except KeyError:
        validas = ", ".join(FUENTES)
        raise ValueError(f"Fuente desconocida: '{codigo}'. Válidas: {validas}")


# ---------------------------------------------------------------------------
# Compatibilidad con el formato anterior
# ---------------------------------------------------------------------------
# Se mantiene para que el código que ya importaba FUENTES_ESTADISTICAS
# siga funcionando. Se genera a partir de las FuenteConfig de arriba.
_INSTITUCION = {"sbs_afp": "SBS", "sbs_historico": "SBS", "aios": "AIOS"}
_NOMBRE_ANTERIOR = {
    "sbs_afp": "Boletín Estadístico AFP",
    "sbs_historico": "Boletín Estadístico Histórico",
    "aios": "Boletín Estadístico AIOS",
}

FUENTES_ESTADISTICAS = [
    {
        "institucion": _INSTITUCION[f.codigo],
        "nombre": _NOMBRE_ANTERIOR[f.codigo],
        "url": f.url,
    }
    for f in FUENTES.values()
]

