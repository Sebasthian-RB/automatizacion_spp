
from django.core.management.base import BaseCommand

from fuentes.configuracion import FUENTES_ESTADISTICAS
from fuentes.services.acceso_web import acceder_pagina


class Command(BaseCommand):
    help = "Comprueba el acceso a las páginas estadísticas de SBS y AIOS."

    def handle(self, *args, **options):
        for fuente in FUENTES_ESTADISTICAS:
            self.stdout.write(
                f"\nConsultando {fuente['institucion']}: "
                f"{fuente['nombre']}"
            )

            try:
                resultado = acceder_pagina(fuente["url"])

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Acceso correcto. HTTP: "
                        f"{resultado['codigo_http']}"
                    )
                )
                self.stdout.write(
                    f"Título: {resultado['titulo']}"
                )
                self.stdout.write(
                    f"URL final: {resultado['url_final']}"
                )
                self.stdout.write(
                    f"Caracteres HTML recibidos: "
                    f"{len(resultado['contenido_html'])}"
                )

            except Exception as error:
                self.stderr.write(
                    self.style.ERROR(
                        f"No se pudo acceder a la fuente: {error}"
                    )
                )
