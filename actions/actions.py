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
import json
from services.user_service import guardar_o_actualizar_usuario, obtener_usuario

# Gestion de Claves Api
load_dotenv()
API_KEY = os.getenv("GEOAPIFY_API_KEY")
TK_API_KEY = os.getenv("TKMASTER")

def cargar_i18n():
    # Separo la carga del json para que quede mas limpio, lo vi en un tutorial de youtube
    import os
    ruta = os.path.join(os.path.dirname(__file__), '..', 'data', 'i18n_config.json')
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)

TEXTOS = cargar_i18n()


def es_solo_numeros(texto):
    """Devuelve True si el texto es un número puro (ej: '123', '3')."""
    return texto.strip().lstrip('+-').replace('.', '', 1).isdigit()


def obtener_coords(ciudad):
    url = "https://api.geoapify.com/v1/geocode/search"

    params = {"text": ciudad + ", Spain", "limit": 1, "apiKey": API_KEY}

    try:
        response = requests.get(url, params=params, timeout=4)
        data = response.json()
    except requests.RequestException:
        return None, None

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


def detectar_idioma(texto):
    if not texto:
        return "es"
    texto = texto.lower()
    palabras_ingles = TEXTOS["deteccion_idioma"]["palabras_clave_en"]
    for palabra in palabras_ingles:
        if f" {palabra} " in f" {texto} " or texto.startswith(f"{palabra} ") or texto.endswith(f" {palabra}") or texto == palabra:
            return "en"
    return "es"


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


def buscar_en_wikipedia(monumento, idioma="es"):
    url = f"https://{idioma}.wikipedia.org/w/api.php"
    # IMPORTANTE: Wikipedia bloqueaba las llamadas y daba error 403, me volvi loco buscando en google. 
    # Hay que poner el User-Agent si o si para que sepan que es un proyecto
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
        response = requests.get(url, params=params, headers=headers, timeout=4)
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


def traducir_es_en(texto):
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": texto, "langpair": "es|en"}
        r = requests.get(url, params=params, timeout=3)
        if r.status_code == 200:
            tr = r.json().get("responseData", {}).get("translatedText")
            if tr:
                return tr
    except:
        pass
    return texto

def obtener_resumen_wikipedia(titulo, idioma="es", idioma_ui=None):
    if idioma_ui is None:
        idioma_ui = idioma
    titulo_encoded = urllib.parse.quote(titulo.replace(" ", "_"))
    url = f"https://{idioma}.wikipedia.org/api/rest_v1/page/summary/{titulo_encoded}"

    # CAMBIO: mantener User-Agent tambien en endpoint REST de resumen.
    headers = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}

    try:
        response = requests.get(url, headers=headers, timeout=4)

        if response.status_code != 200 or not response.text:
            return None

        data = response.json()

        # CAMBIO: Rechazar páginas de desambiguación de Wikipedia.
        # La API REST devuelve type="disambiguation" para estas páginas.
        # Además se comprueba la descripción por si el campo type no está presente.
        tipo_pagina = data.get("type", "")
        descripcion = data.get("description", "")
        terminos_disambig = ["desambiguación", "disambiguation", "wikimedia disambiguation"]
        if tipo_pagina == "disambiguation" or any(t in descripcion.lower() for t in terminos_disambig):
            print(f"[Wikipedia] Rechazada página de desambiguación: '{data.get('title', titulo)}'")
            return None

        extract = data.get("extract", "")
        link = data.get("content_urls", {}).get("desktop", {}).get("page", "")

        # Recortar extract a máximo 3 frases
        frases = extract.split(". ")
        resumen_corto = ". ".join(frases[:3]).strip()
        if resumen_corto and not resumen_corto.endswith("."):
            resumen_corto += "."

        if not resumen_corto:
            return None

        if idioma == "es" and idioma_ui == "en":
            if descripcion:
                descripcion = traducir_es_en(descripcion)
            resumen_corto = traducir_es_en(resumen_corto)

        resultado = f" *{titulo}*"
        if descripcion:
            resultado += f"\n_{descripcion}_"
        resultado += f"\n\n{resumen_corto}"
        if link:
            if idioma_ui == "en":
                resultado += f"\n\nMore info: {link}"
            else:
                resultado += f"\n\nMás info: {link}"

        return resultado

    except Exception as e:
        # TODO: Mejorar este print porque a veces sale en consola y asusta
        print("ERROR Wikipedia summary:", e)
        return None


def tiene_info_wikipedia(nombre, idioma="es", ciudad=None):
    """
    Comprueba rapidamente si un monumento tiene articulo valido en Wikipedia.
    Usa opensearch con el nombre exacto (sin ciudad) porque opensearch no
    soporta consultas compuestas y devuelve [] si hay palabras extra.
    Si se encuentra titulo, se valida similitud con difflib.
    Si el resultado es una disambiguation page, se descarta.
    """
    try:
        url = f"https://{idioma}.wikipedia.org/w/api.php"
        headers = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}
        # IMPORTANTE: NO añadir ciudad al query de opensearch.
        # opensearch es muy literal y devuelve [] si el query no encaja exacto
        # con el título del artículo. La ciudad se usaba antes pero rompía
        # monumentos famosos como "Sagrada Família barcelona" → sin resultados.
        params = {
            "action": "opensearch",
            "search": nombre,
            "limit": 1,
            "format": "json",
        }
        response = requests.get(url, params=params, headers=headers, timeout=2)
        data = response.json()
        # opensearch devuelve [query, [titulos], [descripciones], [urls]]
        titulos = data[1] if len(data) > 1 else []
        descripciones = data[2] if len(data) > 2 else []
        if titulos:
            titulo = titulos[0]
            descripcion_resultado = descripciones[0].lower() if descripciones else ""
            # Descartar páginas de desambiguación
            terminos_disambig = ["desambiguación", "disambiguation"]
            if any(t in descripcion_resultado for t in terminos_disambig):
                return False
            if get_close_matches(nombre.lower(), [titulo.lower()], cutoff=0.3):
                return True
    except Exception:
        pass
    return False


class ActionBuscarMonumentos(Action):

    def name(self):
        return "action_buscar_monumentos"

    def run(self, dispatcher, tracker, domain):

        mensaje = tracker.latest_message.get("text") or ""
        idioma = detectar_idioma(mensaje.lower())

        # Rechazar entradas puramente numéricas
        if es_solo_numeros(mensaje.strip()):
            dispatcher.utter_message(text=TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["ciudad_no_encontrada"].format(ciudad=mensaje.strip()))
            return []

        #  detectar si es monumento
        if any(
            palabra in mensaje.lower()
            for palabra in [
                " de ",
                " del ",
                "palacio",
                "convento",
                "catedral",
                "iglesia",
                "monasterio",
                "castillo",
                "castle",
                "cathedral",
                "church",
                "palace",
                "information about",
                "info about",
                "tell me about",
            ]
        ):
            dispatcher.utter_message(text=TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["parece_monumento"])
            return [FollowupAction("action_info_monumento")]

        ciudad = tracker.get_slot("ciudad")
        ciudad_mensaje = extraer_ciudad_del_mensaje(tracker)
        if ciudad_mensaje:
            ciudad = ciudad_mensaje
        else:
            # CAMBIO: Si el NLU no extrae entidad ciudad, intentar detectarla desde
            # la última palabra del mensaje. Esto permite cambiar de ciudad en la misma
            # sesión aunque el slot ya tenga un valor anterior (ej: "quiero visitar llanes")
            texto_original = tracker.latest_message.get("text", "")
            palabras = texto_original.split()
            if palabras:
                # Limpiar puntuación final
                candidata = palabras[-1].lower().strip().rstrip(".,!?")
                palabras_ignoradas = [
                    "monumentos", "ver", "visitar", "sitios", "lugares", "informacion",
                    "eventos", "conciertos", "teatro", "deporte", "partido", "festival",
                    "musica", "actividades", "planes", "recomendaciones", "sugerencias"
                ]
                # Solo usamos la candidata si es distinta a la ciudad actual del slot,
                # no es un número puro, no es una palabra ignorada, y tiene al menos 2 caracteres
                if candidata and candidata not in palabras_ignoradas and candidata != (ciudad or "").lower() and not es_solo_numeros(candidata) and len(candidata) >= 2:
                    ciudad = candidata

        # fallback final si no hay ciudad de ningún modo
        if not ciudad:
            texto = tracker.latest_message.get("text", "")
            palabras = texto.split()
            if palabras:
                candidata_final = palabras[-1].lower().strip().rstrip(".,!?")
                palabras_ignoradas = [
                    "monumentos", "ver", "visitar", "sitios", "lugares", "informacion",
                    "eventos", "conciertos", "teatro", "deporte", "partido", "festival",
                    "musica", "actividades", "planes", "recomendaciones", "sugerencias"
                ]
                if candidata_final not in palabras_ignoradas and not es_solo_numeros(candidata_final) and len(candidata_final) >= 2:
                    ciudad = candidata_final

        # Evitar fallo si Mongo no funciona porque a veces me olvido de levantar el docker
        try:
            mensaje = tracker.latest_message.get("text")
            intent = tracker.latest_message.get("intent").get("name")
            guardar_log(intent, ciudad, mensaje)
        except Exception as e:
            print("Error log:", e)

        #  si no hay ciudad
        if not ciudad:
            dispatcher.utter_message(text=TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["pedir_ciudad"])
            return []

        #  obtener coordenadas dinámicamente
        lat, lon = obtener_coords(ciudad)

        if not lat or not lon:
            dispatcher.utter_message(text=TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["ciudad_no_encontrada"].format(ciudad=ciudad))
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
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            lugares = []

            for lugar in data.get("features", []):
                props = lugar.get("properties", {})
                nombre = props.get("name")
                if not nombre:
                    continue

                # Estrategia B: si Geoapify ya incluye tag wikidata/wikipedia
                # en los metadatos del lugar, sabemos que tiene articulo sin
                # necesidad de hacer ninguna llamada adicional.
                raw = props.get("datasource", {}).get("raw", {})
                tiene_wikidata = bool(raw.get("wikidata") or raw.get("wikipedia"))

                # Estrategia A: si no tiene tag, verificar directamente en
                # Wikipedia con opensearch y timeout corto (2s).
                # Se pasa la ciudad como contexto geografico para evitar
                # falsos positivos de lugares homonimos en otros paises.
                if tiene_wikidata or tiene_info_wikipedia(nombre, idioma, ciudad=ciudad):
                    lugares.append(nombre)

            if lugares:
                respuesta = TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["resultado_exito"].format(ciudad=ciudad.capitalize())
                for l in lugares:
                    respuesta += f"- {l}\n"
            else:
                respuesta = TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["resultado_vacio"].format(ciudad=ciudad)

            dispatcher.utter_message(text=respuesta)

        except Exception as e:
            dispatcher.utter_message(text=TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["error_api"])
            print(f"[ERROR ActionBuscarMonumentos] tipo={type(e).__name__} detalle={e}")

        return [SlotSet("ciudad", ciudad)]


class ActionBuscarEventos(Action):

    def name(self):
        return "action_buscar_eventos"

    def run(self, dispatcher, tracker, domain):

        ciudad = tracker.get_slot("ciudad")
        ciudad_mensaje = extraer_ciudad_del_mensaje(tracker)
        texto_msg = tracker.latest_message.get("text") or ""
        idioma_pre = detectar_idioma(texto_msg.lower())

        # Rechazar entradas puramente numéricas
        if es_solo_numeros(texto_msg.strip()):
            dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma_pre]["pedir_ciudad"])
            return []

        if ciudad_mensaje:
            ciudad = ciudad_mensaje
        else:
            palabras = texto_msg.split()
            if palabras:
                candidata = palabras[-1].lower().strip().rstrip(".,!?")
                palabras_ignoradas = [
                    "monumentos", "ver", "visitar", "sitios", "lugares", "informacion",
                    "eventos", "conciertos", "teatro", "deporte", "partido", "festival",
                    "musica", "actividades", "planes", "recomendaciones", "sugerencias"
                ]
                if candidata and candidata not in palabras_ignoradas and candidata != (ciudad or "").lower() and not es_solo_numeros(candidata) and len(candidata) >= 2:
                    ciudad = candidata

        # fallback final si no hay ciudad de ningún modo
        if not ciudad:
            palabras = texto_msg.split()
            if palabras:
                candidata_final = palabras[-1].lower().strip().rstrip(".,!?")
                palabras_ignoradas = [
                    "monumentos", "ver", "visitar", "sitios", "lugares", "informacion",
                    "eventos", "conciertos", "teatro", "deporte", "partido", "festival",
                    "musica", "actividades", "planes", "recomendaciones", "sugerencias"
                ]
                if candidata_final not in palabras_ignoradas and not es_solo_numeros(candidata_final) and len(candidata_final) >= 2:
                    ciudad = candidata_final

        mensaje = tracker.latest_message.get("text", "").lower()
        idioma = detectar_idioma(mensaje)

        if not ciudad:
            dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["pedir_ciudad_corta"])
            return []
            
        ciudad = ciudadNormalizada(ciudad)

        if not ciudad:
            dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["pedir_ciudad"])
            return []
        
        # Determinar el tipo de evento basado en el mensaje
        classification = ""
        if "teatro" in mensaje:
            classification = "Arts & Theatre"
        elif "concierto" in mensaje or "festival" in mensaje or "musica" in mensaje:
            classification = "Music"
        elif "deporte" in mensaje or "partido" in mensaje:
            classification = "Sports"

        url = "https://app.ticketmaster.com/discovery/v2/events.json"
        params = {
            "apikey": TK_API_KEY,
            "countryCode": "ES",
            "city": ciudad,
            "size": 5,
            "sort": "date,asc"
        }
        
        if classification:
            params["classificationName"] = classification

        try:
            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                eventos_encontrados = data.get("_embedded", {}).get("events", [])
                
                if eventos_encontrados:
                    respuesta = TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["resultado_exito"].format(ciudad=ciudad.capitalize())
                    enlace_texto = TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["enlace_entradas"]

                    for evento in eventos_encontrados:
                        nombre = evento.get("name", "Evento sin nombre")
                        url_evento = evento.get("url", "")

                        # Fecha y hora del evento
                        fechas = evento.get("dates", {}).get("start", {})
                        fecha = fechas.get("localDate", "")   # ej: "2025-06-14"
                        hora  = fechas.get("localTime", "")   # ej: "20:00:00"
                        fecha_fmt = ""
                        if fecha:
                            partes = fecha.split("-")
                            if len(partes) == 3:
                                fecha_fmt = f"{partes[2]}/{partes[1]}/{partes[0]}"
                        if hora:
                            fecha_fmt += f" {hora[:5]}h"

                        # Rango de precio (no siempre esta disponible en Ticketmaster)
                        precios = evento.get("priceRanges", [])
                        precio_fmt = ""
                        if precios:
                            pmin = precios[0].get("min")
                            pmax = precios[0].get("max")
                            cur  = precios[0].get("currency", "EUR")
                            if pmin is not None and pmax is not None and pmin != pmax:
                                precio_fmt = f"{pmin:.0f}\u2013{pmax:.0f} {cur}"
                            elif pmin is not None:
                                precio_fmt = f"desde {pmin:.0f} {cur}"

                        # Componer linea con los campos disponibles
                        linea = f"- **{nombre}**"
                        if fecha_fmt:
                            linea += f" \u00b7 \U0001f4c5 {fecha_fmt}"
                        if precio_fmt:
                            linea += f" \u00b7 \U0001f39f {precio_fmt}"
                        if url_evento:
                            linea += f" · [{enlace_texto}]({url_evento})"
                        respuesta += linea + "\n"
                            
                    dispatcher.utter_message(text=respuesta)
                else:
                    dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["resultado_vacio"].format(ciudad=ciudad.capitalize()))
            else:
                dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["error_api"])
                print(f"Error Ticketmaster API: {response.status_code} - {response.text}")
                
        except Exception as e:
            dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["error_conexion"])
            print("Error Exception Ticketmaster:", e)

        return [SlotSet("ciudad", ciudad)]


class ActionRecomendarPlanes(Action):
    def name(self):
        return "action_recomendar_planes"

    def run(self, dispatcher, tracker, domain):

        mensaje = tracker.latest_message.get("text", "").lower()
        idioma = detectar_idioma(mensaje)
        
        ciudad = tracker.get_slot("ciudad")
        ciudad_mensaje = extraer_ciudad_del_mensaje(tracker)
        if ciudad_mensaje:
            ciudad = ciudad_mensaje
        else:
            palabras = tracker.latest_message.get("text", "").split()
            if palabras:
                candidata = palabras[-1].lower().strip().rstrip(".,!?")
                palabras_ignoradas = [
                    "monumentos", "ver", "visitar", "sitios", "lugares", "informacion",
                    "eventos", "conciertos", "teatro", "deporte", "partido", "festival",
                    "musica", "actividades", "planes", "recomendaciones", "sugerencias"
                ]
                if candidata and candidata not in palabras_ignoradas and candidata != (ciudad or "").lower() and not es_solo_numeros(candidata) and len(candidata) >= 2:
                    ciudad = candidata

        if not ciudad:
            palabras = tracker.latest_message.get("text", "").split()
            if palabras:
                candidata_final = palabras[-1].lower().strip().rstrip(".,!?")
                palabras_ignoradas = [
                    "monumentos", "ver", "visitar", "sitios", "lugares", "informacion",
                    "eventos", "conciertos", "teatro", "deporte", "partido", "festival",
                    "musica", "actividades", "planes", "recomendaciones", "sugerencias"
                ]
                if candidata_final not in palabras_ignoradas and not es_solo_numeros(candidata_final) and len(candidata_final) >= 2:
                    ciudad = candidata_final

        if not ciudad:
            dispatcher.utter_message(text=TEXTOS["action_recomendar_planes"]["respuestas"][idioma]["pedir_ciudad"])
            return []

        ciudad = ciudadNormalizada(ciudad)
        if ciudad:
            recomendaciones = TEXTOS["action_recomendar_planes"]["recomendaciones"]
            if ciudad in recomendaciones:
                lista = recomendaciones[ciudad].get(idioma, recomendaciones[ciudad]["es"])
                respuesta = TEXTOS["action_recomendar_planes"]["respuestas"][idioma]["resultado_exito"].format(ciudad=ciudad.capitalize())
                for m in lista:
                    respuesta += f"- {m}\n"
                dispatcher.utter_message(text=respuesta)
            else:
                dispatcher.utter_message(text=TEXTOS["action_recomendar_planes"]["respuestas"][idioma]["no_recomendaciones"])
        else:
            dispatcher.utter_message(text=TEXTOS["action_recomendar_planes"]["respuestas"][idioma]["pedir_ciudad"])
        return [SlotSet("ciudad", ciudad)]


class ActionInfoMonumento(Action):

    def name(self):
        return "action_info_monumento"

    def run(self, dispatcher, tracker, domain):

        mensaje_raw = tracker.latest_message.get("text") or ""
        mensaje = mensaje_raw.lower()
        idioma = detectar_idioma(mensaje)

        # Rechazar entradas puramente numéricas o demasiado cortas
        if es_solo_numeros(mensaje_raw.strip()) or len(mensaje_raw.strip()) < 2:
            dispatcher.utter_message(text=TEXTOS["action_info_monumento"]["respuestas"][idioma]["pedir_monumento"])
            return [SlotSet("monumento", None)]

        # evitar confusión con eventos
        if "festival" in mensaje or "concierto" in mensaje or "teatro" in mensaje or "event" in mensaje or "concert" in mensaje:
            dispatcher.utter_message(text=TEXTOS["action_info_monumento"]["respuestas"][idioma]["parece_evento"])
            return [SlotSet("monumento", None)]

        monumento = tracker.get_slot("monumento")
        # CAMBIO: se elimino reemplazar " de " para no degradar nombres validos.
        # Antes: monumento = monumento.replace(" de ", " ")
        texto = tracker.latest_message.get("text").lower()

        # Validación para detectar extracciones incompletas del NLU (ej: "castillo de") o genéricas ("iglesia")
        es_generico = False
        if monumento:
            mon_limpio = monumento.strip().lower()
            genericos = [
                "castillo", "iglesia", "palacio", "catedral", "convento", "plaza",
                "monasterio", "museo", "parque", "puente", "ermita", "torre", "acueducto",
                "castle", "church", "palace", "cathedral", "convent", "square",
                "museum", "park", "bridge", "tower"
            ]
            if mon_limpio.endswith(" de") or mon_limpio.endswith(" of") or mon_limpio in genericos:
                es_generico = True

        stopwords = TEXTOS["action_info_monumento"].get(f"stopwords_{idioma}", TEXTOS["action_info_monumento"]["stopwords_es"])
        palabras = texto.split()
        palabras_limpias = [p for p in palabras if p not in stopwords]
        monumento_fallback = " ".join(palabras_limpias)

        # Usar fallback si la extracción de Rasa es genérica, muy corta, una preposición, 
        # o si el fallback es claramente más completo que la extracción parcial de Rasa.
        if (not monumento or 
            len(monumento) < 3 or 
            monumento in ["de", "del", "el", "la", "los", "las", "the", "a", "an"] or 
            es_generico or 
            (monumento_fallback and monumento and (monumento in monumento_fallback) and len(monumento_fallback) > len(monumento) + 3)):
            
            monumento = monumento_fallback

        # validación final
        if not monumento or len(monumento.strip()) < 3:
            dispatcher.utter_message(text=TEXTOS["action_info_monumento"]["respuestas"][idioma]["pedir_monumento"])
            return [SlotSet("monumento", None)]

        #  normalizar texto
        monumento = ciudadNormalizada(monumento)
        prefijos = TEXTOS["action_info_monumento"]["prefijos"]
        for prefijo in prefijos:
            if monumento.startswith(prefijo):
                monumento = monumento[len(prefijo) :]
        # Enriquecer busqueda con la ciudad del slot para desambiguar
        # geograficamente (ej: "Casa Puebla Badajoz" en vez de "Casa Puebla")
        ciudad_ctx = tracker.get_slot("ciudad")
        query_wiki = f"{monumento} {ciudad_ctx}" if ciudad_ctx else monumento

        # buscar título en Wikipedia con contexto geografico
        titulo = buscar_en_wikipedia(query_wiki, idioma)

        # Validación: Evitar falsos positivos si el título devuelto es completamente distinto.
        # Cutoff 0.5 para ser más estricto (0.3 era demasiado permisivo y causaba falsos positivos
        # como "Palau Robert" → "Palau Blaugrana").
        if titulo and not get_close_matches(monumento.lower(), [titulo.lower()], cutoff=0.5):
            titulo = None

        idioma_busqueda = idioma

        # Fallback: Si no se encuentra un resultado válido en inglés, buscar en español
        if not titulo and idioma == "en":
            titulo_es = buscar_en_wikipedia(query_wiki, "es")
            if titulo_es and get_close_matches(monumento.lower(), [titulo_es.lower()], cutoff=0.5):
                titulo = titulo_es
                idioma_busqueda = "es"

        if not titulo:
            # CAMBIO: Si no hay ningún título válido tras todas las validaciones,
            # devolver directamente el mensaje de no encontrado sin hacer más búsquedas
            # que puedan traer resultados completamente irrelevantes (ej: Patrimonio de la Humanidad)
            respuesta = TEXTOS["action_info_monumento"]["respuestas"][idioma]["no_encontrado"].format(monumento=monumento)
            dispatcher.utter_message(text=respuesta)
            return [SlotSet("monumento", None)]

        respuesta = obtener_resumen_wikipedia(titulo, idioma_busqueda, idioma_ui=idioma)

        if not respuesta:
            respuesta = TEXTOS["action_info_monumento"]["respuestas"][idioma]["no_encontrado"].format(monumento=monumento)

        dispatcher.utter_message(text=respuesta)
        return [SlotSet("monumento", None)]

class ActionSaludoPersonalizado(Action):
    def name(self):
        return "action_saludo_personalizado"

    def run(self, dispatcher, tracker, domain):
        mensaje = tracker.latest_message.get("text") or ""
        idioma = detectar_idioma(mensaje.lower())
        sender_id = tracker.sender_id
        usuario = obtener_usuario(sender_id)

        if usuario and usuario.nombre:
            respuesta = TEXTOS["action_registro"]["respuestas"][idioma]["saludo_conocido"].format(nombre=usuario.nombre)
            dispatcher.utter_message(text=respuesta)
            return [SlotSet("es_usuario_nuevo", False)]
        else:
            respuesta = TEXTOS["action_registro"]["respuestas"][idioma]["saludo_nuevo"]
            dispatcher.utter_message(text=respuesta)
            return [SlotSet("es_usuario_nuevo", True)]

class ActionRegistrarUsuario(Action):
    def name(self):
        return "action_registrar_usuario"

    def run(self, dispatcher, tracker, domain):
        mensaje = tracker.latest_message.get("text") or ""
        idioma = detectar_idioma(mensaje.lower())
        sender_id = tracker.sender_id
        nombre = tracker.get_slot("nombre")
        ciudad_origen = tracker.get_slot("ciudad_origen")
        pais = tracker.get_slot("pais")

        guardar_o_actualizar_usuario(sender_id, nombre=nombre, ciudad_origen=ciudad_origen, pais=pais)
        
        respuesta = TEXTOS["action_registro"]["respuestas"][idioma]["registro_completado"]
        dispatcher.utter_message(text=respuesta)
        return []

class ActionAskNombre(Action):
    def name(self):
        return "action_ask_nombre"
    
    def run(self, dispatcher, tracker, domain):
        mensaje = tracker.latest_message.get("text") or ""
        idioma = detectar_idioma(mensaje.lower())
        respuesta = TEXTOS["action_registro"]["respuestas"][idioma]["ask_nombre"]
        dispatcher.utter_message(text=respuesta)
        return []

class ActionAskCiudadOrigen(Action):
    def name(self):
        return "action_ask_ciudad_origen"
    
    def run(self, dispatcher, tracker, domain):
        mensaje = tracker.latest_message.get("text") or ""
        idioma = detectar_idioma(mensaje.lower())
        respuesta = TEXTOS["action_registro"]["respuestas"][idioma]["ask_ciudad_origen"]
        dispatcher.utter_message(text=respuesta)
        return []

class ActionAskPais(Action):
    def name(self):
        return "action_ask_pais"
    
    def run(self, dispatcher, tracker, domain):
        mensaje = tracker.latest_message.get("text") or ""
        idioma = detectar_idioma(mensaje.lower())
        respuesta = TEXTOS["action_registro"]["respuestas"][idioma]["ask_pais"]
        dispatcher.utter_message(text=respuesta)
        return []
