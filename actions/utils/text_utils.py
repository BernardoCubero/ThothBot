import unicodedata
from difflib import get_close_matches
from actions.utils.i18n import TEXTOS

def es_solo_numeros(texto):
    """Devuelve True si el texto es un número puro (ej: '123', '3')."""
    return texto.strip().lstrip('+-').replace('.', '', 1).isdigit()

def ciudadNormalizada(texto):
    texto = texto.lower()
    texto = texto.strip()
    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    return texto

def corregir_typos_ciudad(ciudad):
    if not ciudad:
        return ciudad
    ciudad_norm = ciudadNormalizada(ciudad)
    
    # Mapeo directo de inglés y traducciones comunes
    mapeo_ciudades = {
        "seville": "sevilla",
        "saragossa": "zaragoza",
        "majorca": "mallorca",
        "minorca": "menorca",
        "alicant": "alicante"
    }
    if ciudad_norm in mapeo_ciudades:
        return mapeo_ciudades[ciudad_norm]
        
    # Catálogo de ciudades de interés para auto-corregir typos
    ciudades_conocidas = [
        "sevilla", "madrid", "cordoba", "granada", "barcelona", 
        "valencia", "bilbao", "malaga", "zaragoza", "toledo", 
        "salamanca", "segovia", "burgos", "cadiz", "alicante",
        "valladolid", "pedraza"
    ]
    
    # Encontrar la coincidencia más cercana
    coincidencias = get_close_matches(ciudad_norm, ciudades_conocidas, n=1, cutoff=0.68)
    if coincidencias:
        return coincidencias[0]
        
    return ciudad_norm

def detectar_idioma(texto):
    if not texto:
        return "es"
    texto = texto.lower()
    palabras_ingles = TEXTOS["deteccion_idioma"]["palabras_clave_en"]
    for palabra in palabras_ingles:
        if f" {palabra} " in f" {texto} " or texto.startswith(f"{palabra} ") or texto.endswith(f" {palabra}") or texto == palabra:
            return "en"
    return "es"
