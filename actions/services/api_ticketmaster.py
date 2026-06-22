import os
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
