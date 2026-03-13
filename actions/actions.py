import unicodedata
from mongo_logger import guardar_log
from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher

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
        intent = tracker.latest_message.get["intent"].get("name")
        ciudad = tracker.get_slot("ciudad")
        guardar_log(intent, ciudad, mensaje)

        if ciudad:
            ciudad = ciudadNormalizada(ciudad)

            if ciudad in monumentos:

                lista = monumentos[ciudad]

                respuesta = f"En {ciudad.capitalize()} puedes visitar:\n"

                for m in lista:
                    respuesta += f"- {m}\n"

                dispatcher.utter_message(text=respuesta)

            else:
                dispatcher.utter_message(text=f"No tengo información de {ciudad} todavía.")

        else:
            dispatcher.utter_message(text="¿En qué ciudad quieres buscar monumentos?")

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

                lista = eventos[ciudad]

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

        monumento = tracker.get_slot("monumento")

        if monumento:

            monumento = monumento.lower()

            if monumento in info_monumentos:

                respuesta = info_monumentos[monumento]

                dispatcher.utter_message(text=respuesta)

            else:
                dispatcher.utter_message(text="No tengo información sobre ese monumento todavía.")

        else:
            dispatcher.utter_message(text="¿Sobre qué monumento quieres información?")

        return []
