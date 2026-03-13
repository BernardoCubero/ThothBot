from pymongo import MongoClient
from datetime import datetime

cliente = MongoClient('localhost', 27017) # Datos de mi mongo local

db = cliente["thotbot"]

coleccion = db["conversaciones"]

def guardar_log(intent, ciudad, mensaje):

    log = {
        "timestamp": datetime.now(),
        "intent": intent,
        "ciudad": ciudad,
        "mensaje": mensaje
    }

    coleccion.insert_one(log)

