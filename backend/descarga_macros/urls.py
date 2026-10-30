from django.urls import path

from descarga_macros.api import descargar_sbs

urlpatterns = [
    path("descargar/", descargar_sbs, name="sbs-descargar"),
]