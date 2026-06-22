import requests
import urllib.parse
from difflib import get_close_matches
from actions.db.mongo_logger import guardar_error
from actions.services.api_translation import traducir_es_en

def buscar_en_wikipedia(monumento, idioma="es"):
    url = f"https://{idioma}.wikipedia.org/w/api.php"
    headers = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}

    params = {
        "action": "query",
        "list": "search",
        "srsearch": monumento,
        "format": "json",
        "srlimit": 1,
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=4)
    except requests.RequestException as e:
        print("ERROR Wikipedia search:", e)
        guardar_error("Wikipedia Search", "Error de red al buscar en Wikipedia", e)
        return None

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    resultados = data.get("query", {}).get("search", [])

    if resultados:
        titulo = resultados[0]["title"]
        return titulo

    return None

def obtener_resumen_wikipedia(titulo, idioma="es", idioma_ui=None):
    if idioma_ui is None:
        idioma_ui = idioma
    titulo_encoded = urllib.parse.quote(titulo.replace(" ", "_"))
    url = f"https://{idioma}.wikipedia.org/api/rest_v1/page/summary/{titulo_encoded}"

    headers = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}

    try:
        response = requests.get(url, headers=headers, timeout=4)

        if response.status_code != 200 or not response.text:
            return None

        data = response.json()

        tipo_pagina = data.get("type", "")
        descripcion = data.get("description", "")
        terminos_disambig = ["desambiguación", "disambiguation", "wikimedia disambiguation"]
        if tipo_pagina == "disambiguation" or any(t in descripcion.lower() for t in terminos_disambig):
            print(f"[Wikipedia] Rechazada página de desambiguación: '{data.get('title', titulo)}'")
            guardar_error("Wikipedia Summary", "Pagina de desambiguacion rechazada", data.get('title', titulo))
            return None

        extract = data.get("extract", "")
        link = data.get("content_urls", {}).get("desktop", {}).get("page", "")

        frases = extract.split(". ")
        resumen_corto = ". ".join(frases[:3]).strip()
        if resumen_corto and not resumen_corto.endswith("."):
            resumen_corto += "."

        if not resumen_corto:
            return None

        if idioma == "es" and idioma_ui == "en":
            if descripcion:
                descripcion = traducir_es_en(descripcion[:450])
            if resumen_corto:
                resumen_corto = traducir_es_en(resumen_corto[:450])

        resultado = f" *{titulo}*"
        if descripcion:
            resultado += f"\n_{descripcion}_"
        resultado += f"\n\n{resumen_corto}"
        if link:
            if idioma_ui == "en":
                resultado += f"\n\nMore info: {link}"
            else:
                resultado += f"\n\nMás info: {link}"

        return resultado

    except Exception as e:
        print("ERROR Wikipedia summary:", e)
        guardar_error("Wikipedia Summary", "Error al obtener resumen REST", e)
        return None

def tiene_info_wikipedia(nombre, idioma="es", ciudad=None):
    try:
        url = f"https://{idioma}.wikipedia.org/w/api.php"
        headers = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}
        params = {
            "action": "opensearch",
            "search": nombre,
            "limit": 1,
            "format": "json",
        }
        response = requests.get(url, params=params, headers=headers, timeout=1)
        data = response.json()
        titulos = data[1] if len(data) > 1 else []
        descripciones = data[2] if len(data) > 2 else []
        if titulos:
            titulo = titulos[0]
            descripcion_resultado = descripciones[0].lower() if descripciones else ""
            terminos_disambig = ["desambiguación", "disambiguation"]
            if any(t in descripcion_resultado for t in terminos_disambig):
                return False
            if get_close_matches(nombre.lower(), [titulo.lower()], cutoff=0.5):
                return True
    except Exception:
        pass
    return False
