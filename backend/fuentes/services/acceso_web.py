
import requests
from bs4 import BeautifulSoup


def acceder_pagina(url: str) -> dict:
    respuesta = requests.get(
        url,
        timeout=(10, 60),
        headers={
            "User-Agent": "AutomatizacionEstadisticasSPP/1.0",
        },
    )
    respuesta.raise_for_status()

    contenido_html = respuesta.text
    documento = BeautifulSoup(contenido_html, "html.parser")

    return {
        "url_solicitada": url,
        "url_final": respuesta.url,
        "codigo_http": respuesta.status_code,
        "titulo": (
            documento.title.get_text(strip=True)
            if documento.title
            else "Sin título"
        ),
        "contenido_html": contenido_html,
    }
