import os

# 1. Update api_geoapify.py
geo_code = """import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEOAPIFY_API_KEY")

def obtener_coords(ciudad):
    url = "https://api.geoapify.com/v1/geocode/search"
    params = {"text": ciudad + ", Spain", "limit": 1, "apiKey": API_KEY}
    try:
        response = requests.get(url, params=params, timeout=4)
        data = response.json()
    except requests.RequestException:
        return None, None

    if data.get("features"):
        coords = data["features"][0]["geometry"]["coordinates"]
        lon, lat = coords
        return lat, lon

    return None, None

def buscar_lugares_cercanos(lat, lon):
    url = "https://api.geoapify.com/v2/places"
    params = {
        "categories": "tourism.sights,heritage,building.historic,religion.place_of_worship",
        "filter": f"circle:{lon},{lat},8000",
        "bias": f"proximity:{lon},{lat}",
        "limit": 500,
        "apiKey": API_KEY,
    }

    response = requests.get(url, params=params, timeout=10)
    data = response.json()

    ignorados = [
        "homenaje", "estatua", "triunfo", "seminario", "historic centre", "centro histórico",
        "pintura", "área expositiva", "zona arqueológica", "calle", "avenida",
        "glorieta", "rotonda", "monumento a", "mirador", "pináculo", "cruz del", "salam",
        "douglas dc7", "guadalquivir", "placa", "lápida", "busto", "in memoriam", "memorial", 
        "sepultura", "tumba", "cenotafio"
    ]
    nombres_vistos = set()
    candidatos = []

    for lugar in data.get("features", []):
        props = lugar.get("properties", {})
        nombre = props.get("name")
        if not nombre:
            continue
        
        if nombre.lower() in nombres_vistos:
            continue
            
        categories = props.get("categories", [])
        
        exclude_cats = [
            "tourism.sights.memorial",
            "tourism.sights.statue",
            "tourism.attraction.artwork",
            "tourism.sights.information",
            "tourism.sights.map",
            "tourism.sights.signpost"
        ]
        if any(c in categories for c in exclude_cats):
            continue
            
        if any(ign in nombre.lower() for ign in ignorados):
            continue
        
        nombre_lower = nombre.lower()
        if "puerta" in nombre_lower and not any(p in nombre_lower for p in [
            "alcalá", "alcala", "jerez", "sol", "bisagra", "elvira", "serranos", "cuart", "toledo"
        ]):
            continue
        
        palabras = nombre.split()
        if len(palabras) >= 3 and not any(p in nombre.lower() for p in [
            "palacio", "convento", "catedral", "iglesia", "monasterio", "castillo", "templo", 
            "basílica", "santuario", "ermita", "museo", "teatro", "palace", "cathedral", "church", 
            "castle", "museum", "plaza", "parque", "jardín", "puente", "puerta", "arco", "torre", 
            "muralla", "casa", "alcázar", "alcazar", "baños", "banos", "capilla", "sinagoga", 
            "romano", "ruinas", "yacimiento", "monumento"
        ]):
            continue
            
        nombres_vistos.add(nombre.lower())
        
        raw = props.get("datasource", {}).get("raw", {})
        tiene_wikidata = bool(raw.get("wikidata") or raw.get("wikipedia"))
        
        score = 0
        if tiene_wikidata:
            score += 100
        
        es_sight = any(c.startswith("tourism.sight") for c in categories)
        es_attraction = "tourism.attraction" in categories
        es_religion = any(c.startswith("religion.place_of_worship") for c in categories)
        
        if es_attraction:
            score += 80
        elif es_sight:
            score += 40
            
        if es_religion:
            score += 10
        
        if any(term in nombre_lower for term in [
            "mezquita", "catedral", "alcázar", "alcazar", "sinagoga", "castillo", "palacio", "teatro romano", "puente romano"
        ]):
            score += 50
        
        if any(term in nombre_lower for term in [
            "real", "nacional", "prado", "alcalá", "alcala", "debod", "almudena", "viana", "reina sofía", 
            "reina sofia", "bellas artes", "giralda", "plaza de españa", "plaza de espana", "maría luisa", "maria luisa",
            "toro", "torre del oro"
        ]):
            score += 100
        
        distancia_km = props.get("distance", 0) / 1000.0
        score -= distancia_km
        
        candidatos.append((score, nombre))

    candidatos.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in candidatos[:10]]
"""
with open("actions/services/api_geoapify.py", "w") as f:
    f.write(geo_code)


# 2. Create api_ticketmaster.py
tm_code = """import os
import requests
from dotenv import load_dotenv
from actions.db.mongo_logger import guardar_error

load_dotenv()
TK_API_KEY = os.getenv("TKMASTER")

def buscar_eventos(ciudad, classification=None):
    url = "https://app.ticketmaster.com/discovery/v2/events.json"
    params = {
        "apikey": TK_API_KEY,
        "countryCode": "ES",
        "city": ciudad,
        "size": 5,
        "sort": "date,asc"
    }
    
    if classification:
        params["classificationName"] = classification

    try:
        response = requests.get(url, params=params, timeout=5)

        if response.status_code == 200:
            data = response.json()
            eventos_encontrados = data.get("_embedded", {}).get("events", [])
            
            resultados = []
            for evento in eventos_encontrados:
                item = {
                    "nombre": evento.get("name", "Evento sin nombre"),
                    "url": evento.get("url", ""),
                    "fecha_fmt": "",
                    "precio_fmt": ""
                }

                fechas = evento.get("dates", {}).get("start", {})
                fecha = fechas.get("localDate", "")
                hora  = fechas.get("localTime", "")
                if fecha:
                    partes = fecha.split("-")
                    if len(partes) == 3:
                        item["fecha_fmt"] = f"{partes[2]}/{partes[1]}/{partes[0]}"
                if hora:
                    item["fecha_fmt"] += f" {hora[:5]}h"

                precios = evento.get("priceRanges", [])
                if precios:
                    pmin = precios[0].get("min")
                    pmax = precios[0].get("max")
                    cur  = precios[0].get("currency", "EUR")
                    if pmin is not None and pmax is not None and pmin != pmax:
                        item["precio_fmt"] = f"{pmin:.0f}-{pmax:.0f} {cur}"
                    elif pmin is not None:
                        item["precio_fmt"] = f"desde {pmin:.0f} {cur}"

                resultados.append(item)
            return resultados
        else:
            print(f"Error Ticketmaster API: {response.status_code} - {response.text}")
            guardar_error("Ticketmaster", f"Error API status {response.status_code}", response.text)
            return None
    except Exception as e:
        print("Error Exception Ticketmaster:", e)
        guardar_error("Ticketmaster", "Excepcion al buscar eventos", e)
        return None
"""
with open("actions/services/api_ticketmaster.py", "w") as f:
    f.write(tm_code)

# 3. Patch actions/actions.py
with open("actions/actions.py", "r") as f:
    content = f.read()

import re

# Patch imports
content = content.replace("from actions.services.api_geoapify import obtener_coords", 
                          "from actions.services.api_geoapify import obtener_coords, buscar_lugares_cercanos\\nfrom actions.services.api_ticketmaster import buscar_eventos")

# Patch geoapify
geo_start = content.find('url = "https://api.geoapify.com/v2/places"')
geo_end = content.find('lugares = [c[1] for c in candidatos[:10]]') + len('lugares = [c[1] for c in candidatos[:10]]')
if geo_start != -1 and geo_end != -1:
    geo_replacement = "        try:\n            lugares = buscar_lugares_cercanos(lat, lon)"
    content = content[:geo_start] + geo_replacement + content[geo_end:]

# Patch ticketmaster
tm_start = content.find('url = "https://app.ticketmaster.com/discovery/v2/events.json"')
tm_end_str = 'guardar_error("Ticketmaster", "Excepcion al buscar eventos", e)'
tm_end = content.find(tm_end_str) + len(tm_end_str)
if tm_start != -1 and tm_end != -1:
    tm_replacement = """        try:
            eventos = buscar_eventos(ciudad, classification)
            if eventos is not None:
                if eventos:
                    respuesta = TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["resultado_exito"].format(ciudad=ciudad.capitalize())
                    enlace_texto = TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["enlace_entradas"]
                    
                    for evento in eventos:
                        linea = f"- **{evento['nombre']}**"
                        if evento.get('fecha_fmt'):
                            linea += f" \u00b7 {evento['fecha_fmt']}"
                        if evento.get('precio_fmt'):
                            linea += f" \u00b7 \U0001f39f {evento['precio_fmt']}"
                        if evento.get('url'):
                            nombre_corto = evento['nombre'][:25] + "..." if len(evento['nombre']) > 25 else evento['nombre']
                            linea += f" · [🎟 {enlace_texto} - {nombre_corto}]({evento['url']})"
                        respuesta += linea + "\\n"
                        
                    dispatcher.utter_message(text=respuesta)
                else:
                    dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["resultado_vacio"].format(ciudad=ciudad.capitalize()))
            else:
                dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["error_api"])
                
        except Exception as e:
            dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["error_conexion"])
            print("Error Exception Eventos:", e)
            guardar_error("Ticketmaster", "Excepcion al procesar eventos en actions", e)"""
    content = content[:tm_start] + tm_replacement + content[tm_end:]

with open("actions/actions.py", "w") as f:
    f.write(content)

print("All patched!")
