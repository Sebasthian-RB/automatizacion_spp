from pathlib import Path

from django.core.management.base import BaseCommand

from fuentes.configuracion import FUENTES_ESTADISTICAS
from fuentes.services.acceso_web import acceder_pagina
 
 
class Command(BaseCommand):
    help = "Diagnostica el acceso a las páginas estadísticas."
 
    def handle(self, *args, **options):
        for fuente in FUENTES_ESTADISTICAS:
            self.stdout.write(
                f"\n{'=' * 65}\n"
                f"{fuente['institucion']}: {fuente['nombre']}"
            )
 
            try:
                resultado = acceder_pagina(fuente["url"])
 
                if fuente["nombre"] == "Boletín Estadístico AFP":
                    from pathlib import Path
 
                    ruta_diagnostico = (
                        Path.cwd()
                        / "diagnostico_sbs_afp.html"
                    )
 
                    ruta_diagnostico.write_text(
                        resultado["contenido_html"],
                        encoding="utf-8",
                    )
 
                    self.stdout.write(
                        f"HTML de diagnóstico: {ruta_diagnostico}"
                    )
 
                self.stdout.write(
                    f"HTTP: {resultado['codigo_http']}"
                )
                self.stdout.write(
                    f"Título: {resultado['titulo']}"
                )
                self.stdout.write(
                    f"URL final: {resultado['url_final']}"
                )
                self.stdout.write(
                    f"Caracteres HTML: "
                    f"{len(resultado['contenido_html'])}"
                )
                self.stdout.write(
                    f"Enlaces encontrados: "
                    f"{len(resultado['enlaces'])}"
                )
                self.stdout.write(
                    f"Formularios: "
                    f"{len(resultado['formularios'])}"
                )
                self.stdout.write(
                    f"Iframes: {resultado['iframes']}"
                )
                self.stdout.write(
                    f"Etiquetas script: {resultado['scripts']}"
                )
 
                self.stdout.write("\nTexto visible:")
                self.stdout.write(resultado["texto_visible"])
 
                self.stdout.write("\nPrimeros enlaces:")
                for enlace in resultado["enlaces"][:15]:
                    self.stdout.write(
                        f"- {enlace['texto'][:100]} "
                        f"| {enlace['url']}"
                    )
 
            except Exception as error:
                self.stderr.write(
                    self.style.ERROR(f"Error: {error}")
                )
 
 