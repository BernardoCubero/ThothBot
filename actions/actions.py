import unicodedata
from rasa.shared.core.events import FollowupAction
from actions.db.mongo_logger import guardar_log
from rasa_sdk import Action
from rasa_sdk.events import SlotSet
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
    "puente romano": "Puente_Romano_de_Córdoba",
}

monumentos = {
    "cordoba": [
        "Mezquita de Córdoba",
        "Puente Romano",
        "Alcázar de los Reyes Cristianos",
    ]
}
recomendaciones = {
    "cordoba": [
        "Visitar la Mezquita de Córdoba",
        "Pasear por la Judería",
        "Ver el Puente Romano al atardecer",
    ],
    "granada": [
        "Visitar la Alhambra",
        "Pasear por el Albaicín",
        "Ver el Mirador de San Nicolás",
    ],
    "sevilla": [
        "Visitar la Plaza de España",
        "Entrar en el Real Alcázar",
        "Pasear por el barrio de Triana",
    ],
}
eventos = {
    "cordoba": [
        "Festival flamenco",
        "Concierto en el centro",
        "Teatro en el Gran Teatro",
    ]
}
info_monumentos = {
    "alhambra": "La Alhambra es un complejo palaciego y fortaleza situado en Granada, construido durante el reino nazarí.",
    "mezquita de córdoba": "La Mezquita-Catedral de Córdoba es uno de los monumentos más importantes del arte islámico en España.",
    "puente romano": "El Puente Romano de Córdoba cruza el río Guadalquivir y fue construido durante la época romana.",
}


def obtener_coords(ciudad):
    url = "https://api.geoapify.com/v1/geocode/search"

    params = {"text": ciudad + ", Spain", "limit": 1, "apiKey": API_KEY}

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("features"):
        coords = data["features"][0]["geometry"]["coordinates"]
        lon, lat = coords
        return lat, lon

    return None, None


def ciudadNormalizada(texto):
    texto = texto.lower()
    texto = texto.strip()
    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return texto


def extraer_ciudad_del_mensaje(tracker):
    # Prioriza entidad ciudad del ultimo mensaje para permitir cambiar de ciudad.
    entities = tracker.latest_message.get("entities") or []
    for entidad in entities:
        if entidad.get("entity") == "ciudad" and entidad.get("value"):
            return entidad.get("value")

    # Si el intent es solo ciudad, usar el texto completo como nuevo valor.
    intent = (tracker.latest_message.get("intent") or {}).get("name")
    texto = (tracker.latest_message.get("text") or "").strip()
    if intent == "consultar_ciudad" and texto:
        return texto

    return None


def buscar_en_wikipedia(monumento):
    url = "https://es.wikipedia.org/w/api.php"
    # CAMBIO: Wikipedia exige User-Agent en la API de busqueda (evita 403).
    headers = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}

    params = {
        "action": "query",
        "list": "search",
        "srsearch": monumento,
        "format": "json",
        "srlimit": 1,
    }

    # CAMBIO: peticion robusta con timeout y control de errores de red.
    try:
        response = requests.get(url, params=params, headers=headers, timeout=12)
    except requests.RequestException as e:
        print("ERROR Wikipedia search:", e)
        return None

    if response.status_code != 200:
        return None

    # CAMBIO: proteger parseo JSON para no romper la accion con respuestas invalidas.
    try:
        data = response.json()
    except ValueError:
        return None

    resultados = data.get("query", {}).get("search", [])

    if resultados:
        titulo = resultados[0]["title"]
        return titulo  # Ej: "Mezquita-Catedral de Córdoba"

    return None


def obtener_resumen_wikipedia(titulo):
    titulo_encoded = urllib.parse.quote(titulo.replace(" ", "_"))
    url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{titulo_encoded}"

    # CAMBIO: mantener User-Agent tambien en endpoint REST de resumen.
    headers = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}

    try:
        response = requests.get(url, headers=headers)

        if response.status_code != 200 or not response.text:
            return None

        data = response.json()

        descripcion = data.get("description", "")
        extract = data.get("extract", "")
        link = data.get("content_urls", {}).get("desktop", {}).get("page", "")

        # Recortar extract a máximo 3 frases
        frases = extract.split(". ")
        resumen_corto = ". ".join(frases[:3]).strip()
        if resumen_corto and not resumen_corto.endswith("."):
            resumen_corto += "."

        if not resumen_corto:
            return None

        resultado = f" *{titulo}*"
        if descripcion:
            resultado += f"\n_{descripcion}_"
        resultado += f"\n\n{resumen_corto}"
        if link:
            resultado += f"\n\n🔗 Más info: {link}"

        return resultado

    except Exception as e:
        print("ERROR Wikipedia summary:", e)
        return None


class ActionBuscarMonumentos(Action):

    def name(self):
        return "action_buscar_monumentos"

    def run(self, dispatcher, tracker, domain):

        mensaje = tracker.latest_message.get("text").lower()

        #  detectar si es monumento
        if any(
            palabra in mensaje
            for palabra in [
                " de ",
                " del ",
                "palacio",
                "convento",
                "catedral",
                "iglesia",
                "monasterio",
                "castillo",
            ]
        ):
            dispatcher.utter_message(
                text="Eso parece un monumento. Voy a darte información."
            )
            return [FollowupAction("action_info_monumento")]

        ciudad = tracker.get_slot("ciudad")
        ciudad_mensaje = extraer_ciudad_del_mensaje(tracker)
        if ciudad_mensaje:
            ciudad = ciudad_mensaje

        # luego fallback
        if not ciudad:
            texto = tracker.latest_message.get("text")
            palabras = texto.split()

            if palabras:
                ciudad = palabras[-1]

        # Revitar fallo si Mongo no funciona
        try:
            mensaje = tracker.latest_message.get("text")
            intent = tracker.latest_message.get("intent").get("name")
            guardar_log(intent, ciudad, mensaje)
        except Exception as e:
            print("Error log:", e)

        #  si no hay ciudad
        if not ciudad:
            dispatcher.utter_message(text="¿En qué ciudad quieres buscar monumentos?")
            return []

        #  obtener coordenadas dinámicamente
        lat, lon = obtener_coords(ciudad)

        if not lat or not lon:
            dispatcher.utter_message(text=f"No encontré la ciudad {ciudad}.")
            return []

        # llamada a Geoapify
        url = "https://api.geoapify.com/v2/places"

        params = {
            "categories": "tourism.sights",
            "filter": f"circle:{lon},{lat},5000",
            "limit": 10,
            "apiKey": API_KEY,
        }

        try:
            response = requests.get(url, params=params)
            data = response.json()

            lugares = []

            for lugar in data.get("features", []):
                nombre = lugar["properties"].get("name")
                if nombre:
                    lugares.append(nombre)

            if lugares:
                respuesta = f"En {ciudad.capitalize()} puedes visitar:\n"
                for l in lugares:
                    respuesta += f"- {l}\n"
            else:
                respuesta = f"No encontré monumentos en {ciudad}."

            dispatcher.utter_message(text=respuesta)

        except Exception as e:
            dispatcher.utter_message(
                text="Hubo un problema al consultar los monumentos."
            )
            print(e)

        return [SlotSet("ciudad", ciudad)]


class ActionBuscarEventos(Action):

    def name(self):
        return "action_buscar_eventos"

    def run(self, dispatcher, tracker, domain):

        ciudad = tracker.get_slot("ciudad")
        ciudad_mensaje = extraer_ciudad_del_mensaje(tracker)
        if ciudad_mensaje:
            ciudad = ciudad_mensaje

        if not ciudad:
            texto = tracker.latest_message.get("text")
            palabras = texto.split()

            if palabras:
                ciudad = palabras[-1]

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

        return [SlotSet("ciudad", ciudad)]


class ActionRecomendarPlanes(Action):
    def name(self):
        return "action_recomendar_planes"

    def run(self, dispatcher, tracker, domain):

        ciudad = tracker.get_slot("ciudad")
        ciudad_mensaje = extraer_ciudad_del_mensaje(tracker)
        if ciudad_mensaje:
            ciudad = ciudad_mensaje

        if not ciudad:
            dispatcher.utter_message(text="¿En que ciudad quieres recomendaciones?")
            return []

        ciudad = ciudadNormalizada(ciudad)
        if ciudad:
            ciudad = ciudadNormalizada(ciudad)
            if ciudad in recomendaciones:
                lista = recomendaciones[ciudad]
                respuesta = f"En {ciudad.capitalize()} te recomiendo:\n"
                for m in lista:
                    respuesta += f"- {m}\n"
                dispatcher.utter_message(text=respuesta)
            else:
                dispatcher.utter_message(
                    text="Todavia no dispongo de recomendaciones para esa ciudad."
                )
        else:
            dispatcher.utter_message(text="¿En que ciudad quieres recomendaciones?")
        return [SlotSet("ciudad", ciudad)]


class ActionInfoMonumento(Action):

    def name(self):
        return "action_info_monumento"

    def run(self, dispatcher, tracker, domain):

        mensaje = tracker.latest_message.get("text").lower()

        # evitar confusión con eventos
        if "festival" in mensaje or "concierto" in mensaje or "teatro" in mensaje:
            dispatcher.utter_message(
                text="Eso parece un evento. Puedes preguntarme por eventos en una ciudad."
            )
            return []

        monumento = tracker.get_slot("monumento")
        # CAMBIO: se elimino reemplazar " de " para no degradar nombres validos.
        # Antes: monumento = monumento.replace(" de ", " ")
        texto = tracker.latest_message.get("text").lower()

        # 🔥 reconstrucción inteligente si el slot falla
        if not monumento or len(monumento) < 3 or monumento == "de":

            stopwords = [
                "que",
                "es",
                "de",
                "la",
                "el",
                "dime",
                "algo",
                "sobre",
                "informacion",
                "sabes",
            ]

            palabras = texto.split()
            palabras_limpias = [p for p in palabras if p not in stopwords]

            if palabras_limpias:
                monumento = " ".join(palabras_limpias)

        # validación final
        if not monumento or len(monumento.strip()) < 3:
            dispatcher.utter_message(text="¿Sobre qué monumento quieres información?")
            return []

        #  normalizar texto
        monumento = ciudadNormalizada(monumento)
        for prefijo in ["la ", "el ", "los ", "las "]:
            if monumento.startswith(prefijo):
                monumento = monumento[len(prefijo) :]
        # buscar título en Wikipedia
        titulo = buscar_en_wikipedia(monumento)

        if not titulo:
            titulo = monumento

        respuesta = obtener_resumen_wikipedia(titulo)

        if not respuesta:
            respuesta = f"No encontré información fiable sobre '{monumento}'."

        dispatcher.utter_message(text=respuesta)
        return []
