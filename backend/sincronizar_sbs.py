"""
Sincronización REPRODUCIBLE de los archivos de la SBS (colócalo junto a manage.py).

Descarga todo lo que esté publicado y todavía no tengas (o que esté alterado), y omite lo que ya
tienes íntegro (se comprueba contra el manifiesto: tamaño + sha256). Se puede ejecutar cuantas veces
quieras: la segunda vez no descarga nada nuevo salvo los meses recién publicados.

Uso (desde backend/, con el entorno virtual activado):
    python sincronizar_sbs.py --simular                       # sólo muestra el plan, sin abrir el navegador
    python sincronizar_sbs.py                                 # sincroniza todo, desde 1996 hasta hoy
    python sincronizar_sbs.py --desde 2024                    # sólo desde 2024
    python sincronizar_sbs.py --recursos boletin_informativo_mensual --desde 2025 --hasta 2026
    python sincronizar_sbs.py --forzar --desde 2025 --hasta 2025   # vuelve a bajar aunque ya exista

Requisitos: sesión de Windows iniciada y pantalla desbloqueada (el algoritmo mueve el cursor).
Para ABORTAR: lleva el mouse a la esquina superior izquierda.
"""
import argparse
import os
import sys
import time

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.conf import settings  # noqa: E402

from descarga_macros import navegador as n  # noqa: E402

ETIQUETAS = {
    "descargado": "[OK]      ",
    "ya_descargado": "[=]       ",
    "no_disponible": "[--]      ",
    "error": "[ERROR]   ",
    "no_procesado": "[PENDIENTE]",
}


def _p(anio, mes):
    return f"{anio}-{mes:02d}" if anio else "(sin período)"


def sincronizar(clave, args):
    pendientes, omitidos = n.planificar(clave, args.desde, args.hasta, args.forzar, not args.sin_hash)
    print(f"\n== {clave} ==")
    print(f"   ya descargados e íntegros: {len(omitidos)}   |   por descargar: {len(pendientes)}")
    if args.simular or not pendientes:
        if pendientes:
            por_anio = {}
            for a, m in pendientes:
                por_anio.setdefault(a, []).append(m)
            for a, ms in por_anio.items():
                print(f"   {a}: meses {', '.join(f'{m:02d}' for m in ms)}")
        return {"descargado": 0, "error": 0, "no_disponible": 0}, False

    cuenta = {"descargado": 0, "ya_descargado": 0, "no_disponible": 0, "error": 0, "no_procesado": 0}
    abortado = False
    cooldown = int(getattr(settings, "SBS_COOLDOWN_SEGUNDOS", 30)) + 2
    trozos = [pendientes[i:i + args.lote] for i in range(0, len(pendientes), args.lote)]
    for i, trozo in enumerate(trozos, 1):
        if i > 1:
            print(f"   (pausa de {cooldown}s entre sesiones)")
            time.sleep(cooldown)
        print(f"   Sesión {i}/{len(trozos)}: {len(trozo)} período(s). No toques el mouse.")
        try:
            resultados = n.descargar_lote(clave, trozo, forzar=args.forzar,
                                          incluir_detalle=True, max_periodos=args.lote)
        except n.ErrorDescargaSBS as exc:
            print(f"   [ERROR] {exc.codigo}: {exc.mensaje_publico}  {exc.detalle}")
            return cuenta, True
        for r in resultados:
            cuenta[r["estado"]] += 1
            extra = ""
            if r["estado"] == "descargado":
                extra = f"{r['archivo']} ({r['bytes']} bytes)"
            elif r["estado"] == "error":
                extra = f"{r['error']}  {r.get('detalle', '')}"
            elif r.get("revisar_captura"):
                extra = "no se encontró un mes antiguo: revisa la captura del mes o del año"
            print(f"   {ETIQUETAS[r['estado']]} {_p(r['anio'], r['mes'])}  {extra}")
            if r.get("abortado"):
                abortado = True
        if abortado:
            print("   Se detuvo la sincronización para no seguir controlando el cursor.")
            break
    return cuenta, abortado


def main():
    ap = argparse.ArgumentParser(description="Sincroniza (descarga lo que falte) los archivos de la SBS.")
    ap.add_argument("--recursos", nargs="*", help="claves del catálogo (por defecto, todas las de tipo período)")
    ap.add_argument("--desde", type=int, help="año inicial (por defecto 1996)")
    ap.add_argument("--hasta", type=int, help="año final (por defecto, el actual)")
    ap.add_argument("--lote", type=int, default=12, help="períodos por sesión de navegador (por defecto 12)")
    ap.add_argument("--forzar", action="store_true", help="volver a descargar aunque ya esté íntegro")
    ap.add_argument("--simular", action="store_true", help="sólo muestra el plan; no abre el navegador")
    ap.add_argument("--sin-hash", action="store_true", help="verificar sólo el tamaño (más rápido), no el sha256")
    args = ap.parse_args()
    if not 1 <= args.lote <= 60:
        ap.error("--lote debe estar entre 1 y 60")

    claves = args.recursos or [c for c, r in n.RECURSOS_SBS.items()
                               if r.get("periodo") and r.get("activo", True)]
    desconocidas = [c for c in claves if c not in n.RECURSOS_SBS]
    if desconocidas:
        ap.error(f"recursos desconocidos: {', '.join(desconocidas)}")

    hubo_error = hubo_abort = False
    for clave in claves:
        try:
            cuenta, abortado = sincronizar(clave, args)
        except n.ErrorDescargaSBS as exc:
            print(f"[ERROR] {clave}: {exc.codigo} {exc.detalle}")
            sys.exit(2)
        hubo_error |= cuenta.get("error", 0) > 0
        hubo_abort |= abortado
        if not args.simular:
            print(f"   Resumen {clave}: {cuenta}")
        if abortado:
            break
    sys.exit(2 if hubo_abort else 1 if hubo_error else 0)


if __name__ == "__main__":
    main()