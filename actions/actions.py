import unicodedata
from actions.db.mongo_logger import guardar_log
from rasa_sdk import Action
from difflib import get_close_matches
from dotenv import load_dotenv
import os
import requests
import urllib.parse

# Gestion de Claves Api
load_dotenv()
API_KEY = os.getenv("GEOAPIFY_API_KEY")

alias_monumentos = {
    "mezquita": "Mezquita_Catedral_de_Córdoba",
    "alhambra": "Alhambra",
    "puente romano": "Puente_Romano_de_Córdoba"
}

monumentos = {
    "cordoba": [
        "Mezquita de Córdoba",
        "Puente Romano",
        "Alcázar de los Reyes Cristianos"
    ]
}
recomendaciones = {
    "cordoba": [
        "Visitar la Mezquita de Córdoba",
        "Pasear por la Judería",
        "Ver el Puente Romano al atardecer"
    ],
    "granada": [
        "Visitar la Alhambra",
        "Pasear por el Albaicín",
        "Ver el Mirador de San Nicolás"
    ],
    "sevilla": [
        "Visitar la Plaza de España",
        "Entrar en el Real Alcázar",
        "Pasear por el barrio de Triana"
    ]
}
eventos = {
    "cordoba": [
        "Festival flamenco",
        "Concierto en el centro",
        "Teatro en el Gran Teatro"
    ]
}
info_monumentos = {
    "alhambra": "La Alhambra es un complejo palaciego y fortaleza situado en Granada, construido durante el reino nazarí.",
    "mezquita de córdoba": "La Mezquita-Catedral de Córdoba es uno de los monumentos más importantes del arte islámico en España.",
    "puente romano": "El Puente Romano de Córdoba cruza el río Guadalquivir y fue construido durante la época romana."
}


def ciudadNormalizada(texto):
    texto = texto.lower()
    texto = texto.strip()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto


class ActionBuscarMonumentos(Action):

    def name(self):
        return "action_buscar_monumentos"

    def run(self, dispatcher, tracker, domain):

        ciudad = tracker.get_slot("ciudad")

        mensaje = tracker.latest_message.get("text")
        intent = tracker.latest_message.get("intent").get("name")
        guardar_log(intent, ciudad, mensaje)

        if not ciudad:
            dispatcher.utter_message(text="¿En qué ciudad quieres buscar monumentos?")
            return []

        ciudad_norm = ciudadNormalizada(ciudad)

        # Coordenadas básicas (luego lo mejoramos con geocoding)
        coords = {
            "cordoba": (37.8882, -4.7794),
            "sevilla": (37.3891, -5.9845),
            "granada": (37.1773, -3.5986)
        }

        if ciudad_norm not in coords:
            dispatcher.utter_message(text=f"No tengo coordenadas para {ciudad}.")
            return []

        lat, lon = coords[ciudad_norm]

        url = "https://api.geoapify.com/v2/places"

        params = {
            "categories": "tourism.sights",
            "filter": f"circle:{lon},{lat},2000",
            "limit": 5,
            "apiKey": API_KEY
        }

        response = requests.get(url, params=params)
        
        try:
            response = requests.get(url, params=params)
            data = response.json()

            lugares = []

            for lugar in data.get("features", []):
                nombre = lugar["properties"].get("name")
                if nombre:
                    lugares.append(nombre)

            if lugares:
                respuesta = f"Estos son algunos lugares interesantes en {ciudad.capitalize()}:\n"
                for l in lugares:
                    respuesta += f"- {l}\n"
            else:
                respuesta = f"No encontré monumentos en {ciudad}."

            dispatcher.utter_message(text=respuesta)

        except Exception as e:
            dispatcher.utter_message(text="Hubo un problema al consultar los monumentos.")
            print(e)

        return []


class ActionBuscarEventos(Action):

    def name(self):
        return "action_buscar_eventos"

    def run(self, dispatcher, tracker, domain):

        ciudad = tracker.get_slot("ciudad")

        if not ciudad:
            dispatcher.utter_message(text="¿En que ciudad?")
            return []
        ciudad = ciudadNormalizada(ciudad)

        if ciudad:

            if ciudad in eventos:

                mensaje = tracker.latest_message.get("text").lower()

                lista = eventos[ciudad]

                # Filtrado por tipo
                if "teatro" in mensaje:
                    lista = [e for e in lista if "teatro" in e.lower()]

                elif "concierto" in mensaje:
                    lista = [e for e in lista if "concierto" in e.lower()]

                elif "festival" in mensaje:
                    lista = [e for e in lista if "festival" in e.lower()]

                respuesta = f"En {ciudad.capitalize()} puedes asistir a:\n"

                for e in lista:
                    respuesta += f"- {e}\n"

                dispatcher.utter_message(text=respuesta)

            else:
                dispatcher.utter_message(text="No tengo eventos para esta ciudad.")

        else:
            dispatcher.utter_message(text="¿En qué ciudad quieres buscar eventos?")

        return []


class ActionRecomendarPlanes(Action):
    def name(self):
        return "action_recomendar_planes"

    def run(self, dispatcher, tracker, domain):
        ciudad = tracker.get_slot("ciudad")
        if ciudad:
            ciudad = ciudadNormalizada(ciudad)
            if ciudad in recomendaciones:
                lista = recomendaciones[ciudad]
                respuesta = f"En {ciudad.capitalize()} te recomiendo:\n"
                for m in lista:
                    respuesta += f"- {m}\n"
                dispatcher.utter_message(text=respuesta)
            else:
                dispatcher.utter_message(text="Todavia no dispongo de recomendaciones para esa ciudad.")
        else:
            dispatcher.utter_message(text="¿En que ciudad quieres recomendaciones?")
        return []


class ActionInfoMonumento(Action):

    def name(self):
        return "action_info_monumento"

    def run(self, dispatcher, tracker, domain):

        mensaje = tracker.latest_message.get("text").lower()

        # Detectar si es un evento
        if "festival" in mensaje or "concierto" in mensaje or "teatro" in mensaje:
            dispatcher.utter_message(text="Eso parece un evento. Puedes preguntarme por eventos en una ciudad.")
            return []

        monumento = tracker.get_slot("monumento")

        if monumento:

            monumento = ciudadNormalizada(monumento)

            if monumento in alias_monumentos:
                monumento_api = alias_monumentos[monumento]
            else:
                monumento_api = monumento.replace(" ", "_")

            monumento_api_encoded = urllib.parse.quote(monumento_api)

            url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{monumento_api_encoded}"

            try:
                headers = {
                    "User-Agent": "ThothBot/1.0 (proyecto TFG)"
                }

                response = requests.get(url, headers=headers)

                print("STATUS:", response.status_code)
                print("URL:", url)

                if response.status_code == 200:
                    data = response.json()

                    if "extract" in data:
                        respuesta = data["extract"]
                    else:
                        respuesta = "No encontré información sobre ese monumento."

                else:
                    respuesta = f"Error en Wikipedia: {response.status_code}"

            except Exception as e:
                respuesta = "Hubo un problema al consultar la información."
                print("ERROR:", e)

            dispatcher.utter_message(text=respuesta)

        else:
            dispatcher.utter_message(text="¿Sobre qué monumento quieres información?")

        return []
