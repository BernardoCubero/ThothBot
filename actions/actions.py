from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.executor import Tracker

class ActionBuscarMonumentos(Action):
    def name(self):
        return "action_buscar_monumentos"
    def run(self, dispatcher, tracker, domain):
        ciudad = tracker.get_slot('ciudad')
        if ciudad:
            dispatcher.utter_message(text=f"Buscando monumento en {ciudad}")
        else:
            dispatcher.utter_message(text="¿En qué ciudad quieres ver monumentos")

        return[]
