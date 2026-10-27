
from django.db import models


class FuenteDatos(models.Model):
    class Institucion(models.TextChoices):
        SBS = "SBS", "Superintendencia de Banca, Seguros y AFP"
        AIOS = "AIOS", "Asociación Internacional de Organismos de Supervisión de Fondos de Pensiones"
        OTRA = "OTRA", "Otra institución"

    class MetodoExtraccion(models.TextChoices):
        ARCHIVO = "ARCHIVO", "Descarga directa de archivo"
        HTML = "HTML", "Extracción de tabla HTML"
        API = "API", "Consumo de API"
        PDF = "PDF", "Extracción de documento PDF"
        NAVEGADOR = "NAVEGADOR", "Navegación automatizada"

    institucion = models.CharField(
        max_length=10,
        choices=Institucion.choices,
    )
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)

    url_publicacion = models.URLField(max_length=1000)
    url_recurso = models.URLField(max_length=1000, blank=True)

    metodo_extraccion = models.CharField(
        max_length=20,
        choices=MetodoExtraccion.choices,
    )
    formato = models.CharField(max_length=20, blank=True)
    frecuencia = models.CharField(max_length=30, blank=True)

    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["institucion", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["institucion", "nombre"],
                name="uq_fuente_institucion_nombre",
            )
        ]

    def __str__(self):
        return f"{self.institucion} - {self.nombre}"

class RecursoFuente(models.Model):
    class Estado(models.TextChoices):
        DETECTADO = "DETECTADO", "Detectado"
        DESCARGADO = "DESCARGADO", "Descargado"
        ERROR = "ERROR", "Error"

    fuente = models.ForeignKey(
        "fuentes.FuenteDatos",
        on_delete=models.PROTECT,
        related_name="recursos",
    )
    titulo = models.CharField(max_length=500)
    url = models.URLField(max_length=2000, unique=True)
    formato = models.CharField(max_length=20, blank=True)
    descubierto_en = models.DateTimeField(auto_now=True)
    descargado_en = models.DateTimeField(null=True, blank=True)
    ruta_archivo = models.TextField(blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    estado = models.CharField(
        max_length=15,
        choices=Estado.choices,
        default=Estado.DETECTADO,
    )
    detalle_error = models.TextField(blank=True)

    class Meta:
        ordering = ["fuente", "titulo"]

    def __str__(self):
        return f"{self.fuente.nombre} - {self.titulo}"
