import os
import time
import requests
from dotenv import load_dotenv
from codecarbon import OfflineEmissionsTracker

load_dotenv()
API_KEY = os.getenv("GEOAPIFY_API_KEY")
def simulate_bot_workload():
    print("[TEST] Iniciando simulación de carga del bot...")
    
    # 1. Geocodificación de la ciudad
    url_geo = "https://api.geoapify.com/v1/geocode/search"
    params_geo = {"text": "Sevilla, Spain", "limit": 1, "apiKey": API_KEY}
    res_geo = requests.get(url_geo, params=params_geo).json()
    lon, lat = res_geo["features"][0]["geometry"]["coordinates"]
    
    # 2. Obtención de 500 candidatos de Geoapify (Gran volumen de datos)
    url_places = "https://api.geoapify.com/v2/places"
    params_places = {
        "categories": "tourism.sights,heritage,building.historic,religion.place_of_worship",
        "filter": f"circle:{lon},{lat},8000",
        "bias": f"proximity:{lon},{lat}",
        "limit": 500,
        "apiKey": API_KEY,
    }
    res_places = requests.get(url_places, params=params_places).json()
    features = res_places.get("features", [])
    
    # 3. Simulación de procesamiento de filtrado premium y ordenamiento de alta calidad
    ignorados = [
        "homenaje", "estatua", "triunfo", "seminario", "historic centre", "centro histórico",
        "pintura", "área expositiva", "zona arqueológica", "calle", "avenida",
        "glorieta", "rotonda", "monumento a", "mirador", "pináculo", "cruz del", "salam",
        "douglas dc7", "guadalquivir", "placa", "lápida", "busto", "in memoriam", "memorial", 
        "sepultura", "tumba", "cenotafio"
    ]
    
    nombres_vistos = set()
    candidatos = []
    
    for lugar in features:
        props = lugar.get("properties", {})
        nombre = props.get("name")
        if not nombre:
            continue
        if nombre.lower() in nombres_vistos:
            continue
            
        categories = props.get("categories", [])
        
        # Exclusión de micro-monumentos
        exclude_cats = [
            "tourism.sights.memorial", "tourism.sights.statue", "tourism.attraction.artwork",
            "tourism.sights.information", "tourism.sights.map", "tourism.sights.signpost"
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
            
        # Filtro de personas de 3 palabras
        palabras = nombre.split()
        if len(palabras) >= 3 and not any(p in nombre_lower for p in [
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
    top_10 = [c[1] for c in candidatos[:10]]
    print(f"[TEST] Simulación completada con éxito. Encontrados {len(top_10)} monumentos principales.")

if __name__ == "__main__":
    print("=============================================================")
    print("     MEDICIÓN DE EFICIENCIA ENERGÉTICA CON CODECARBON")
    print("=============================================================")
    
    # Inicializar el seguidor de emisiones offline (perfecto para España 'ESP')
    tracker = OfflineEmissionsTracker(country_iso_code="ESP")
    
    # Iniciar la medición de energía consumida por CPU, RAM y GPU
    tracker.start()
    
    start_time = time.time()
    
    try:
        # Ejecutar la simulación de consultas
        simulate_bot_workload()
    finally:
        # Detener la medición y calcular emisiones
        emisiones = tracker.stop()
        end_time = time.time()
        
        duration = end_time - start_time
        print("\n=============================================================")
        print("                 MÉTRICAS DE SOSTENIBILIDAD                  ")
        print("=============================================================")
        print(f"⏱️  Duración del ciclo: {duration:.4f} segundos")
        print(f"⚡  Consumo de energía estimado: {tracker.final_emissions_data.cpu_energy * 1000:.6f} mWh (Miliwatts-hora)")
        print(f"🌱  Emisiones de CO2 equivalent: {emisiones * 1000000:.6f} mg de CO2")
        print(f"💾  Archivo guardado: emissions.csv (guardado con éxito)")
        print("=============================================================")
