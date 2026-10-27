
from django.contrib import admin

from .models import FuenteDatos


@admin.register(FuenteDatos)
class FuenteDatosAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "institucion",
        "metodo_extraccion",
        "frecuencia",
        "activo",
    )
    list_filter = (
        "institucion",
        "metodo_extraccion",
        "activo",
    )
    search_fields = ("nombre", "descripcion", "url_publicacion")
    list_editable = ("activo",)
