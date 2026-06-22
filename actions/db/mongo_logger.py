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

coleccion_errores = db["errores"]

def guardar_error(modulo, descripcion, detalles=None):
    error_log = {
        "timestamp": datetime.now(),
        "modulo": modulo,
        "descripcion": str(descripcion),
        "detalles": str(detalles) if detalles else None
    }
    coleccion_errores.insert_one(error_log)
