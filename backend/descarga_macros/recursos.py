"""
Catálogo CERRADO de recursos de la SBS que se pueden descargar.

Seguridad: el cliente de la API nunca envía URLs ni coordenadas; sólo envía la CLAVE
del recurso y, si el recurso es "periodo": True, un año y un mes (enteros validados).
Todo lo que el algoritmo hace con el navegador y el cursor queda definido aquí.

Acciones soportadas en "pasos":
  {"accion": "esperar", "segundos": 5}
  {"accion": "click_imagen", "imagen": "boton.png", "timeout": 15, "confianza": 0.85}
      opcionales:
        "dx": 30, "dy": 40       -> clic desplazado respecto a la imagen encontrada
        "debajo_de": "anio_{anio}.png" -> sólo acepta la coincidencia POR DEBAJO de esa otra
                                    captura (distingue el "Enero" de cada año)
        "scroll": -400           -> si no la ve, desplaza la página y reintenta (años lejanos)
        "alt": True              -> Alt+clic (descarga el destino del enlace)
  {"accion": "click_relativo", "x": 0.50, "y": 0.40}   # fracciones 0..1 de la pantalla
  {"accion": "mover_relativo", "x": 0.55, "y": 0.60}   # sólo mueve el cursor (para que el scroll actúe en ese panel)
  {"accion": "scroll", "cantidad": -400}               # negativo = hacia abajo
  {"accion": "guardar_como", "extension": ".xlsx"}     # Ctrl+S manual
  {"accion": "aceptar_guardar_como", "extension": ".zip", "timeout": 12, "opcional": True}
      # si el navegador muestra "Guardar como" tras el clic, escribe una ruta temporal nuestra y acepta

Cualquier paso admite:
  "solo_si_anio": {"min": 1996, "max": 2024}   (sólo se ejecuta para esos años)
  "una_vez": "etiqueta"                        (sólo la primera vez en cada sesión de navegador)

Un recurso "periodo": True se descarga en una sesión así:
  pasos_inicio      -> una vez al abrir el navegador (menús)
  pasos_por_anio    -> cada vez que se pasa a otro año
  pasos_por_periodo -> por cada mes (clic en el mes + aceptar el diálogo si aparece)
Un recurso sin período usa sólo "pasos".
Opcionales: "timeout_total" (base de la sesión), "timeout_por_periodo", "timeout_descarga",
"verificar_zip" (patrón que debe aparecer dentro del .zip), "activo": False (excluye de la sincronización).

Plantillas en "imagen"/"debajo_de" para recursos "periodo": {anio} -> 2019 ; {mes} -> enero ... diciembre
  p.ej. "anio_{anio}.png" -> anio_2019.png ,  "mes_{mes}.png" -> mes_marzo.png

Las capturas van en backend/descarga_macros/referencias_ui/ (solo .png).
"""

RECURSOS_SBS = {
    # Boletines Mensuales > Boletín Informativo Mensual (desde 1996). Uso: anio=1996..actual, mes=1..12
    #   * 2025 y 2026 ya están desplegados en la pantalla.
    #   * 2024 y anteriores: hay que abrir "Años anteriores" y luego el año (acordeón).
    "boletin_informativo_mensual": {
        "url": "https://www.sbs.gob.pe/app/stats_net/stats/EstadisticaBoletinEstadistico.aspx?p=31",
        "periodo": True,
        # Se descarga un .zip (p. ej. FP-1231-en2026.zip) que contiene el Excel "Bolweb 01_2026".
        # El módulo NO lo descomprime: eso se hace después, en tu proceso de carga.
        "extensiones": {".zip"},
        # El zip debe contener el período pedido (p. ej. "Bolweb 03_2025"); si no, se rechaza.
        # Si los años antiguos nombran distinto el Excel interno, ajusta o quita esta línea.
        "verificar_zip": "{mes:02d}_{anio}",
        "timeout_total": 90,
        "timeout_por_periodo": 90,
        "timeout_descarga": 90,

        "pasos_inicio": [
            {"accion": "esperar", "segundos": 6},
            {"accion": "click_imagen", "imagen": "menu_boletines_mensuales.png", "timeout": 20},
            {"accion": "esperar", "segundos": 2},
            {"accion": "click_imagen", "imagen": "sub_boletin_informativo_mensual.png", "timeout": 20},
            {"accion": "esperar", "segundos": 3},
        ],

        # Al cambiar de año (sólo 2024 y anteriores): abrir "Años anteriores" (una vez) y luego el año.
        "pasos_por_anio": [
            {"accion": "click_imagen", "imagen": "anios_anteriores.png", "timeout": 20,
             "solo_si_anio": {"max": 2024}, "una_vez": "anios_anteriores"},
            {"accion": "esperar", "segundos": 1, "solo_si_anio": {"max": 2024}, "una_vez": "anios_anteriores"},
            # cursor sobre el panel derecho para que el scroll actúe ahí (no en el menú izquierdo)
            {"accion": "mover_relativo", "x": 0.55, "y": 0.60, "solo_si_anio": {"max": 2024}},
            {"accion": "click_imagen", "imagen": "anio_{anio}.png", "timeout": 60, "scroll": -400,
             "solo_si_anio": {"max": 2024}},
            {"accion": "esperar", "segundos": 1, "solo_si_anio": {"max": 2024}},
        ],

        # Por cada mes: clic en el mes POR DEBAJO del rótulo de su año.
        "pasos_por_periodo": [
            # 2024 y anteriores: si el bloque queda fuera de pantalla, hace scroll
            {"accion": "click_imagen", "imagen": "mes_{mes}.png", "timeout": 40,
             "debajo_de": "anio_{anio}.png", "scroll": -200, "solo_si_anio": {"max": 2024}},
            # 2025 y 2026: ya visibles; un timeout corto basta (si no está, el mes aún no se publicó)
            {"accion": "click_imagen", "imagen": "mes_{mes}.png", "timeout": 8,
             "debajo_de": "anio_{anio}.png", "solo_si_anio": {"min": 2025}},
            # Si el navegador pide dónde guardar, se acepta con una ruta temporal nuestra.
            {"accion": "aceptar_guardar_como", "extension": ".zip", "timeout": 12, "opcional": True},
        ],
    },
}