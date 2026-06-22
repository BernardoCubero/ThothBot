import os
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
