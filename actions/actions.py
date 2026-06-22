from rasa_sdk.events import FollowupAction
from actions.db.mongo_logger import guardar_log, guardar_error
from rasa_sdk import Action
from rasa_sdk.events import SlotSet
from dotenv import load_dotenv
import os
import requests
import urllib.parse
import json
from services.user_service import guardar_o_actualizar_usuario, obtener_usuario

from actions.utils.i18n import TEXTOS
from actions.utils.text_utils import es_solo_numeros, ciudadNormalizada, corregir_typos_ciudad, detectar_idioma
from actions.utils.rasa_utils import extraer_ciudad_del_mensaje

from actions.services.api_geoapify import obtener_coords, buscar_lugares_cercanos\nfrom actions.services.api_ticketmaster import buscar_eventos
from actions.services.api_wikipedia import buscar_en_wikipedia, obtener_resumen_wikipedia, tiene_info_wikipedia
from actions.services.api_translation import traducir_es_en

# Gestion de Claves Api
load_dotenv()
API_KEY = os.getenv("GEOAPIFY_API_KEY")
TK_API_KEY = os.getenv("TKMASTER")


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
                if candidata and candidata not in palabras_ignoradas and candidata != (ciudad or "").lower() and not es_solo_numeros(candidata) and len(candidata) >= 2 and not candidata.startswith("/"):
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
                if candidata_final not in palabras_ignoradas and not es_solo_numeros(candidata_final) and len(candidata_final) >= 2 and not candidata_final.startswith("/"):
                    ciudad = candidata_final

        # Evitar fallo si Mongo no funciona porque a veces me olvido de levantar el docker
        try:
            mensaje = tracker.latest_message.get("text")
            intent = tracker.latest_message.get("intent").get("name")
            guardar_log(intent, ciudad, mensaje)
        except Exception as e:
            print("Error log:", e)
            guardar_error("Mongo Logger", "Error al guardar log de uso", e)

        #  si no hay ciudad
        if not ciudad:
            dispatcher.utter_message(text=TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["pedir_ciudad"])
            return [SlotSet("tipo_busqueda", "monumentos")]

        ciudad = corregir_typos_ciudad(ciudad)

        #  obtener coordenadas dinámicamente
        lat, lon = obtener_coords(ciudad)

        if not lat or not lon:
            dispatcher.utter_message(text=TEXTOS["action_buscar_monumentos"]["respuestas"][idioma]["ciudad_no_encontrada"].format(ciudad=ciudad))
            return []

        # llamada a Geoapify
                try:
            lugares = buscar_lugares_cercanos(lat, lon)

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
            guardar_error("ActionBuscarMonumentos", "Error en la busqueda de monumentos Geoapify", e)

        return [SlotSet("ciudad", ciudad), SlotSet("tipo_busqueda", "monumentos")]


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
                if candidata and candidata not in palabras_ignoradas and candidata != (ciudad or "").lower() and not es_solo_numeros(candidata) and len(candidata) >= 2 and not candidata.startswith("/"):
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
                if candidata_final not in palabras_ignoradas and not es_solo_numeros(candidata_final) and len(candidata_final) >= 2 and not candidata_final.startswith("/"):
                    ciudad = candidata_final

        mensaje = tracker.latest_message.get("text", "").lower()
        idioma = detectar_idioma(mensaje)

        if not ciudad:
            dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["pedir_ciudad_corta"])
            return [SlotSet("tipo_busqueda", "eventos")]
            
        ciudad = corregir_typos_ciudad(ciudad)

        if not ciudad:
            dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["pedir_ciudad"])
            return [SlotSet("tipo_busqueda", "eventos")]
        
        # Determinar el tipo de evento basado en el mensaje
        classification = ""
        if "teatro" in mensaje:
            classification = "Arts & Theatre"
        elif "concierto" in mensaje or "festival" in mensaje or "musica" in mensaje:
            classification = "Music"
        elif "deporte" in mensaje or "partido" in mensaje:
            classification = "Sports"

                try:
            eventos = buscar_eventos(ciudad, classification)
            if eventos is not None:
                if eventos:
                    respuesta = TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["resultado_exito"].format(ciudad=ciudad.capitalize())
                    enlace_texto = TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["enlace_entradas"]
                    
                    for evento in eventos:
                        linea = f"- **{evento['nombre']}**"
                        if evento.get('fecha_fmt'):
                            linea += f" · {evento['fecha_fmt']}"
                        if evento.get('precio_fmt'):
                            linea += f" · 🎟 {evento['precio_fmt']}"
                        if evento.get('url'):
                            nombre_corto = evento['nombre'][:25] + "..." if len(evento['nombre']) > 25 else evento['nombre']
                            linea += f" · [🎟 {enlace_texto} - {nombre_corto}]({evento['url']})"
                        respuesta += linea + "\n"
                        
                    dispatcher.utter_message(text=respuesta)
                else:
                    dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["resultado_vacio"].format(ciudad=ciudad.capitalize()))
            else:
                dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["error_api"])
                
        except Exception as e:
            dispatcher.utter_message(text=TEXTOS["action_buscar_eventos"]["respuestas"][idioma]["error_conexion"])
            print("Error Exception Eventos:", e)
            guardar_error("Ticketmaster", "Excepcion al procesar eventos en actions", e)

        return [SlotSet("ciudad", ciudad), SlotSet("tipo_busqueda", "eventos")]


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
            return [SlotSet("tipo_busqueda", "planes")]

        ciudad = corregir_typos_ciudad(ciudad)
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
            return [SlotSet("tipo_busqueda", "planes")]
        return [SlotSet("ciudad", ciudad), SlotSet("tipo_busqueda", "planes")]


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
        texto = ciudadNormalizada(mensaje_raw)

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
        # Ampliar stopwords con preposiciones, artículos y verbos comunes.
        # Necesario porque la imagen Docker puede tener un i18n_config.json antiguo
        # sin las stopwords "hablame", "la", "el", etc. añadidas posteriormente.
        stopwords_extra = {
            "de", "del", "en", "a", "al", "los", "las", "le", "la", "el",
            "hablame", "cuentame", "buscame", "enseñame", "muestrame", "dame",
            "sobre", "acerca", "respecto"
        }
        palabras = texto.split()
        palabras_limpias = [p for p in palabras if p not in stopwords and p not in stopwords_extra]
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
        # geograficamente (ej: "Casa Puebla Badajoz" en vez de "Casa Puebla").
        # IMPORTANTE: no añadir ciudad si monumento ya la contiene o es la misma ciudad,
        # para evitar queries tipo "cordoba Cordoba" o "de cordoba Cordoba".
        ciudad_ctx = corregir_typos_ciudad(tracker.get_slot("ciudad"))
        ciudad_ctx_norm = ciudadNormalizada(ciudad_ctx) if ciudad_ctx else ""
        monumento_norm = ciudadNormalizada(monumento)
        if ciudad_ctx and ciudad_ctx_norm not in monumento_norm:
            query_wiki = f"{monumento} {ciudad_ctx}"
        else:
            query_wiki = monumento

        # buscar título en Wikipedia con contexto geografico
        titulo = buscar_en_wikipedia(query_wiki, idioma)

        def es_match_valido(m, t):
            if not t: return False
            m_n = ciudadNormalizada(m)
            t_n = ciudadNormalizada(t)
            # Coincidencia exacta
            if m_n == t_n:
                return True
            # El título debe EMPEZAR con el query o viceversa.
            if t_n.startswith(m_n) or m_n.startswith(t_n):
                return True
                
            # Validacion estricta por palabras para evitar falsos positivos
            m_w = {w for w in m_n.replace("-", " ").split() if w not in {"de", "la", "el", "del", "en", "a", "of", "the", "in", "and"}}
            t_w = {w for w in t_n.replace("-", " ").split() if w not in {"de", "la", "el", "del", "en", "a", "of", "the", "in", "and"}}
            
            if m_w and t_w:
                overlap = m_w.intersection(t_w)
                overlap_ratio = len(overlap) / min(len(m_w), len(t_w))
                
                # Si todas las palabras significativas coinciden
                if overlap_ratio >= 1.0:
                    return True
                    
                from difflib import SequenceMatcher
                seq_ratio = SequenceMatcher(None, m_n, t_n).ratio()
                
                # Exigir un buen solapamiento de palabras Y buena secuencia, o una secuencia casi perfecta
                # Esto rechaza 'catedral segovia' vs 'andres segovia' (overlap=0.5, seq=0.73)
                return (overlap_ratio >= 0.5 and seq_ratio >= 0.80) or seq_ratio >= 0.90
            
            from difflib import SequenceMatcher
            return SequenceMatcher(None, m_n, t_n).ratio() >= 0.85

        # Validación: Evitar falsos positivos si el título devuelto es completamente distinto.
        if titulo and not es_match_valido(monumento, titulo):
            titulo = None

        # Fallback directo: si la búsqueda no dio un título válido, intentar buscar
        # el artículo EXACTO por nombre en Wikipedia (primero via search, luego REST).
        # Útil para ciudades y lugares conocidos (ej: "cordoba" → artículo "Córdoba").
        if not titulo:
            # Intentar con el nombre capitalizado directamente
            nombre_directo = monumento.strip().title()
            # Buscar via search API y exigir que el título devuelto sea exactamente
            # lo que pedimos (no solo que lo contenga)
            titulo_directo = buscar_en_wikipedia(nombre_directo, idioma)
            if titulo_directo and ciudadNormalizada(titulo_directo) == ciudadNormalizada(nombre_directo):
                titulo = titulo_directo
            else:
                # Intentar obtener el artículo directamente por URL (la API REST
                # hace redirect automático para acentos, ej: "Cordoba" → "Córdoba")
                import urllib.parse as _up
                url_test = f"https://{idioma}.wikipedia.org/api/rest_v1/page/summary/{_up.quote(nombre_directo)}"
                headers_test = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}
                try:
                    r_test = requests.get(url_test, headers=headers_test, timeout=4)
                    if r_test.status_code == 200:
                        d_test = r_test.json()
                        titulo_rest = d_test.get("title", "")
                        tipo_rest = d_test.get("type", "")
                        desc_rest = d_test.get("description", "").lower()
                        terminos_disambig = ["desambiguación", "disambiguation", "wikimedia disambiguation"]
                        es_disambig = tipo_rest == "disambiguation" or any(t in desc_rest for t in terminos_disambig)
                        # Solo aceptar si el título REST coincide con lo pedido
                        if not es_disambig and es_match_valido(nombre_directo, titulo_rest):
                            titulo = titulo_rest
                except Exception:
                    pass

        # Fallback españa: si el título es válido pero es una página de desambiguación,
        # intentar con "(España)" para obtener la ciudad española correcta.
        if titulo:
            resumen_test = obtener_resumen_wikipedia(titulo, idioma, idioma_ui=idioma)
            if resumen_test is None:
                # Probablemente desambiguación: intentar con contexto de país
                titulo_esp = buscar_en_wikipedia(f"{titulo} España ciudad", idioma)
                if titulo_esp and es_match_valido(monumento, titulo_esp):
                    titulo = titulo_esp

        idioma_busqueda = idioma

        # Fallback: Si no se encuentra un resultado válido en inglés, buscar en español
        if not titulo and idioma == "en":
            titulo_es = buscar_en_wikipedia(query_wiki, "es")
            if titulo_es and es_match_valido(monumento, titulo_es):
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

class ActionBotChallenge(Action):
    def name(self):
        return "action_bot_challenge"

    def run(self, dispatcher, tracker, domain):
        mensaje = tracker.latest_message.get("text") or ""
        idioma = detectar_idioma(mensaje.lower())
        respuesta = TEXTOS["bot_challenge"]["respuestas"][idioma]["intro"]
        dispatcher.utter_message(text=respuesta)
        return []

class ActionProcesarCiudad(Action):
    def name(self):
        return "action_procesar_ciudad"

    def run(self, dispatcher, tracker, domain):
        tipo_busqueda = tracker.get_slot("tipo_busqueda")
        ciudad = extraer_ciudad_del_mensaje(tracker)
        
        if not ciudad:
            texto_msg = tracker.latest_message.get("text") or ""
            palabras = texto_msg.split()
            if palabras:
                ciudad = palabras[-1].lower().strip().rstrip(".,!?")
                
        events = []
        if ciudad:
            events.append(SlotSet("ciudad", ciudad))
            
        if tipo_busqueda == "eventos":
            events.append(FollowupAction("action_buscar_eventos"))
        elif tipo_busqueda == "planes":
            events.append(FollowupAction("action_recomendar_planes"))
        else:
            events.append(FollowupAction("action_buscar_monumentos"))
            
        return events
