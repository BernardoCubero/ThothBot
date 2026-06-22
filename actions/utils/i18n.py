import os
import json

def cargar_i18n():
    # Separo la carga del json para que quede mas limpio
    ruta = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'i18n_config.json')
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)

TEXTOS = cargar_i18n()
