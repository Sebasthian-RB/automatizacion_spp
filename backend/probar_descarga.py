import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from descarga_macros import navegador as n  # noqa: E402

CLAVE = "boletin_informativo_mensual"


def comprobar(anios):
    recurso = n.RECURSOS_SBS[CLAVE]
    faltan = set()
    for anio in anios:
        for mes in range(1, 13):
            for paso in n._resolver_pasos(recurso["pasos"], anio, mes):
                for campo in ("imagen", "debajo_de"):
                    nombre = paso.get(campo)
                    if nombre and not (n.REFERENCIAS_DIR / nombre).is_file():
                        faltan.add(nombre)
    try:
        import pyautogui
        print("Resolución de pantalla que ve el algoritmo:", tuple(pyautogui.size()))
    except Exception as exc:  # noqa: BLE001
        print("pyautogui no está disponible:", exc)
    print("Carpeta de capturas:", n.REFERENCIAS_DIR)
    if faltan:
        print("FALTAN estas capturas:")
        for nombre in sorted(faltan):
            print("  -", nombre)
    else:
        print("Todo OK: están todas las capturas.")


def descargar(anio, mes):
    print(f"Descargando {CLAVE} {anio}-{mes:02d}. No toques el mouse. "
          "Para abortar: esquina superior izquierda.")
    try:
        print("RESULTADO:", n.descargar_recurso(CLAVE, anio, mes))
    except n.ErrorDescargaSBS as exc:
        print(f"ERROR: {exc.codigo} -> {exc.mensaje_publico}")
    except Exception as exc:  # noqa: BLE001
        print("ERROR inesperado:", repr(exc))


if __name__ == "__main__":
    try:
        accion, *args = sys.argv[1:]
        nums = [int(a) for a in args]
        if accion == "comprobar" and nums:
            comprobar(nums)
        elif accion == "descargar" and len(nums) == 2:
            descargar(*nums)
        else:
            raise ValueError
    except ValueError:
        print("Uso: python probar_descarga.py comprobar 2025 2024")
        print("     python probar_descarga.py descargar 2025 3")