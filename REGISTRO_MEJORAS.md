# Registro de Problemas y Mejoras (ThothBot)

Este documento es un registro de los problemas técnicos que hemos ido encontrando durante el desarrollo y pruebas de ThothBot, así como las soluciones de rendimiento y arquitectura aplicadas para asegurar su correcto funcionamiento.

## 1. Problema de Congelación por Base de Datos
*   **Problema Detectado:** El bot en ocasiones se quedaba pensando infinitamente (o hasta 30 segundos) sin devolver respuesta al usuario.
*   **Causa Raíz:** La librería `pymongo` intentaba conectar sincrónicamente a una instancia local de MongoDB en `mongo_logger.py`. Si el servidor de base de datos no estaba activo, la ejecución se bloqueaba esperando el *timeout* por defecto del driver antes de lanzar la excepción.
*   **Solución Aplicada:** Se ha configurado un `serverSelectionTimeoutMS=2000` en la instancia de `MongoClient`. Ahora, si la base de datos no está disponible, el bloque de código arroja una excepción a los 2 segundos, la cual es capturada por el `try/except` en `actions.py`, permitiendo que el bot responda al usuario de forma ininterrumpida sin guardar el log.

## 2. Bloqueos Indefinidos por Peticiones de Red (APIs)
*   **Problema Detectado:** Lentitud general o congelación del bot al hacer búsquedas de monumentos o información.
*   **Causa Raíz:** Al usar la librería `requests` para conectar con servicios externos (Geoapify, Wikipedia, Ticketmaster), no se habían especificado tiempos máximos de espera (`timeout`) en todas las peticiones. Si el servidor remoto experimentaba latencia, el bot se quedaba colgado indefinidamente.
*   **Solución Aplicada:** Se ha blindado cada petición HTTP con un parámetro `timeout` y control de excepciones (`requests.RequestException`):
    *   Geoapify (`obtener_coords` y `places`): Añadido `timeout=4`.
    *   Wikipedia (`buscar_en_wikipedia` y `obtener_resumen_wikipedia`): Limitado a `timeout=4`.
    *   Ticketmaster (`ActionBuscarEventos`): Limitado a `timeout=5`.

## 3. Fallo de Búsqueda de Monumentos por "Stopwords"
*   **Problema Detectado:** Al introducir frases como *"me das información sobre plaza de españa"*, la búsqueda en Wikipedia devolvía resultados completamente erróneos (ej. el municipio de "Riós").
*   **Causa Raíz:** El algoritmo de extracción de palabras clave (fallback) eliminaba ciertas palabras pero dejaba pronombres y verbos comunes (como "me" y "das"). El buscador de Wikipedia recibía `"me das plaza espana"`, arrojando falsos positivos.
*   **Solución Aplicada:** Se amplió la lista negra de `stopwords` en `ActionInfoMonumento` para incluir: `"me", "das", "puedes", "dar", "decir", "buscar", "por", "favor", "quiero", "ver", "conocer", "un", "una", "los", "las"`. De esta manera se filtra correctamente el nombre del monumento real antes de enviarlo a Wikipedia.

## 4. Transición de Datos Estáticos a Dinámicos (Eventos)
*   **Problema Detectado:** La lista de eventos era un diccionario `dict` estático incrustado en el código fuente.
*   **Causa Raíz:** Diseño inicial de la acción.
*   **Solución Aplicada:** Se eliminó el diccionario y se integró con la API Discovery de Ticketmaster. Se añadió lógica de clasificación (Music, Arts & Theatre, Sports) según las palabras detectadas en el mensaje del usuario, aportando eventos actualizados en tiempo real y URLs de compra de entradas.

## 5. Clasificación Errónea de Intenciones (Overfitting de NLU)
*   **Problema Detectado:** Al preguntar por la ciudad "Córdoba", el bot siempre lanzaba la búsqueda de eventos, mientras que al preguntar por "Sevilla" lanzaba correctamente la de monumentos.
*   **Causa Raíz:** La palabra `cordoba` no estaba incluida en la intención base `consultar_ciudad`, pero aparecía repetidamente como ejemplo de ciudad en `buscar_eventos`. Esto provocaba un sobreajuste (overfitting) en la red neuronal de Rasa, asociando matemáticamente esa palabra a los eventos. Además, había un error de sangría (indentación) en los ejemplos de monumentos en inglés.
*   **Solución Aplicada:** Se equilibró el modelo añadiendo explícitamente `cordoba` a la intención `consultar_ciudad` y se corrigió la sangría en el archivo `nlu.yml` para asegurar que el motor de Rasa procesa todos los ejemplos correctamente y deja de confundir contextos.

## 6. Soporte Bilingüe (Internacionalización - Fase 1)
*   **Problema Detectado:** El usuario formulaba preguntas en inglés (ej. *"Events in Madrid"*) y, aunque el NLU reconocía la intención, el bot siempre contestaba con textos estáticos en español.
*   **Causa Raíz:** Las respuestas de las Custom Actions (`actions.py`) estaban programadas (hardcoded) directamente en español.
*   **Solución Aplicada:** 
    *   Se implementó una función `detectar_idioma(texto)` en Python basada en palabras clave en inglés (*what, events, see...*).
    *   Se modificó dinámicamente el prefijo de la URL de la API de Wikipedia (`es.wikipedia.org` -> `en.wikipedia.org`) si se detecta inglés.
    *   Se tradujeron todas las respuestas, enlaces de compra y mensajes de error de Ticketmaster y Geoapify generados desde las acciones.

## Próximos Pasos Pendientes (Fase 2 de Internacionalización)
*   Dividir las intenciones estáticas de saludos y despedidas en `nlu.yml` (crear `saludo_en`, `despedida_en`).
*   Modificar `domain.yml` y `rules.yml` para mapear los nuevos intents de inglés con sus respectivas respuestas nativas (ej. `utter_saludo_en`), logrando así un soporte bilingüe integral desde el saludo inicial.
