from pymongo import MongoClient
from datetime import datetime


import os
cliente = MongoClient(os.getenv('MONGO_HOST', 'localhost'), 27017, serverSelectionTimeoutMS=2000) # Datos de mi mongo local

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

