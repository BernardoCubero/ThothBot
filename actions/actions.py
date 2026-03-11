from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher

monumentos = {
    "cordoba": [
        "Mezquita de Córdoba",
        "Puente Romano",
        "Alcázar de los Reyes Cristianos"
    ]
}

class ActionBuscarMonumentos(Action):

    def name(self):
        return "action_buscar_monumentos"

    def run(self, dispatcher, tracker, domain):

        ciudad = tracker.get_slot("ciudad")

        if ciudad:
            ciudad = ciudad.lower()

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