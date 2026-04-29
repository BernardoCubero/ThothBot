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

## 7. Falsos Positivos en Búsquedas de Wikipedia en Inglés
*   **Problema Detectado:** Al preguntar en inglés por monumentos muy locales (ej. *"info about castillo lizar"*), el bot respondía con información completamente inconexa, como resúmenes de álbumes de Shakira.
*   **Causa Raíz:** La búsqueda de Wikipedia se hacía en la versión en inglés (`en.wikipedia.org`). Al no existir un artículo en inglés para ese monumento, el motor de búsqueda de Wikipedia devolvía el resultado con la coincidencia más aproximada en su base de datos global (en este caso, un compositor llamado "Lizar" en la página de Shakira). El bot asumía ciegamente que el primer resultado era el correcto.
*   **Solución Aplicada:** Se implementó una doble mejora en `actions.py`:
    1.  **Validación de Similitud:** Se añadió el uso de `get_close_matches` de la librería `difflib` para comparar el título devuelto por Wikipedia con el monumento buscado (exigiendo un mínimo de 30% de similitud). Si no coincide, se descarta el resultado como falso positivo.
    2.  **Fallback Multilingüe:** Si se está buscando en inglés y el resultado se descarta o no se encuentra, el bot hace automáticamente una búsqueda secundaria en la Wikipedia en español. Si encuentra el monumento, se lo devuelve al usuario, asegurando que reciba información útil aunque no esté traducida.

## Pendiente: Fase 2 de Internacionalización (Saludos y Despedidas Bilingües)

> **Estado:** ❌ No completado. La respuesta `utter_saludo_en` existe en `domain.yml` pero no está conectada a ningún intent ni regla — es un callejón sin salida.

El objetivo de esta fase es que el bot detecte el idioma del saludo/despedida inicial y responda en el mismo idioma, de forma nativa, sin depender de la función `detectar_idioma()`.

### Tareas pendientes:

*   **[ ] `data/nlu.yml`** — Separar el intent `saludo` en dos:
    *   `saludo` → solo ejemplos en español (*hola, buenas, buenos días...*)
    *   `saludo_en` → solo ejemplos en inglés (*hello, hi, good morning, hey there...*)
*   **[ ] `data/nlu.yml`** — Separar el intent `despedida` en dos:
    *   `despedida` → solo ejemplos en español (*adiós, hasta luego, nos vemos...*)
    *   `despedida_en` → solo ejemplos en inglés (*goodbye, bye, see you, thanks bye...*)
*   **[ ] `domain.yml`** — Registrar los nuevos intents `saludo_en` y `despedida_en`.
*   **[ ] `domain.yml`** — Añadir la respuesta `utter_despedida_en` en inglés (ej: *"Have a great trip!"*).
*   **[ ] `data/rules.yml`** — Añadir regla: `saludo_en` → `utter_saludo_en`.
*   **[ ] `data/rules.yml`** — Añadir regla: `despedida_en` → `utter_despedida_en`.
*   **[ ] Reentrenar el modelo Rasa** — Ejecutar `rasa train` para que aprenda los nuevos intents.

## 8. Nombres de Monumentos Truncados (Caso Pedro Castillo)
*   **Problema Detectado:** Al preguntar por *"informacion sobre castillo de pedraza"*, el bot respondía con la biografía del expresidente de Perú, "Pedro Castillo".
*   **Causa Raíz:** El NLU detectaba "pedraza" como la entidad `ciudad`, dejando la entidad `monumento` aislada e incompleta como *"castillo de"*. Al buscar exactamente *"castillo de"* en Wikipedia, el primer resultado con alta coincidencia era "Pedro Castillo". Como la palabra "Castillo" coincidía en ambos textos, la validación de similitud implementada lo daba por válido.
*   **Solución Aplicada:** Se programó una capa de inteligencia en `actions.py` que detecta si el monumento extraído por el NLU es sospechoso (si termina en " de", " of", o si es una palabra demasiado genérica como "castillo" o "iglesia"). Cuando detecta este patrón, ignora la extracción truncada del NLU y fuerza el modo *fallback*. Este modo procesa la frase entera, elimina conectores (stopwords) y compone la búsqueda real ("castillo pedraza"), localizando así el monumento correcto en lugar de a un político.

## 9. El Bot No Cambia de Ciudad en la Misma Sesión
*   **Problema Detectado:** Si el usuario había consultado monumentos de "Pedraza" y luego escribía "quiero visitar Llanes", el bot seguía mostrando los monumentos de Pedraza.
*   **Causa Raíz:** El sistema dependía de que el NLU marcara explícitamente la nueva ciudad como entidad `ciudad` en el mensaje. Cuando el intent era `buscar_monumentos` con frases como "quiero visitar X", el NLU clasificaba correctamente la intención pero no etiquetaba "X" como entidad. La función `extraer_ciudad_del_mensaje()` devolvía `None`, y el slot anterior (`ciudad = "pedraza"`) nunca se sobreescribía.
*   **Solución Aplicada:** Se añadió un segundo nivel de detección en `ActionBuscarMonumentos`: cuando el NLU no extrae ninguna entidad ciudad, el bot analiza la última palabra del mensaje del usuario como candidata. Si esa candidata es distinta a la ciudad actualmente almacenada en el slot, se considera un cambio de ciudad y se actualiza. El slot se sobreescribe con `SlotSet("ciudad", ciudad)` al final de la acción, completando el cambio para toda la sesión.

## 10. Monumentos Sin Artículo en Wikipedia Devuelven Información Irrelevante
*   **Problema Detectado:** Al preguntar sobre monumentos muy locales o poco conocidos (ej. *"Cueva de la Argolla"* en Pedraza), el bot respondía con artículos completamente ajenos, como "Patrimonio de la Humanidad".
*   **Causa Raíz:** Cuando la validación de similitud descartaba todos los resultados de Wikipedia por ser falsos positivos, el código hacía `titulo = monumento` y realizaba una búsqueda literal de ese texto. Sin artículo propio, Wikipedia devolvía cualquier cosa vagamente relacionada con alguna palabra del nombre (ej. "cueva" → artículo genérico de "Patrimonio de la Humanidad"). El bot enviaba ese resumen sin más comprobaciones.
*   **Solución Aplicada:** Se eliminó el paso de `titulo = monumento` como último recurso. Ahora, si tras todas las validaciones y fallbacks no se encuentra ningún título fiable, el bot interrumpe el proceso y devuelve directamente el mensaje de "no encontrado" configurado en el `i18n_config.json`, evitando cualquier búsqueda basura adicional.

## 11. El Bot Recomendaba Monumentos de los que No Tenía Información
*   **Problema Detectado:** `ActionBuscarMonumentos` listaba hasta 10 monumentos devueltos por Geoapify sin comprobar si Wikipedia disponía de información sobre ellos. Si el usuario preguntaba posteriormente por uno de esos monumentos, la acción `ActionInfoMonumento` no encontraba artículo válido y devolvía un error de "no encontrado", generando una experiencia contradictoria (el bot lo recomendó pero no sabe nada de él).
*   **Causa Raíz:** El filtrado de la lista de monumentos era puramente nominal: se incluía cualquier lugar que tuviera un campo `name` en la respuesta de Geoapify, independientemente de si existía documentación disponible sobre él.
*   **Solución Aplicada:** Se implementó un filtrado previo en dos estrategias combinadas en `actions.py`:
    1.  **Estrategia B — Tag Wikidata de Geoapify (sin coste):** Antes de añadir un monumento a la lista, se inspecciona el campo `datasource.raw` de la respuesta de Geoapify. Si contiene los tags `wikidata` o `wikipedia`, se confirma directamente que existe artículo disponible sin ninguna llamada adicional.
    2.  **Estrategia A — Verificación Wikipedia como fallback:** Si el lugar no tiene tag Wikidata, se realiza una consulta `opensearch` a la API de Wikipedia con un timeout reducido de 2 segundos. Solo se incluye en la lista si el título devuelto supera el umbral de similitud mínima del 30% con `difflib.get_close_matches`.
*   **Nueva función:** `tiene_info_wikipedia(nombre, idioma)` encapsula esta lógica de verificación rápida, reutilizando el mismo mecanismo de validación de similitud ya empleado en `ActionInfoMonumento`.

## 12. Falsos Positivos Geográficos en Búsquedas de Wikipedia (Monumentos Homónimos)
*   **Problema Detectado:** Al preguntar por *"información de Casa Puebla"* estando en Badajoz, el bot devolvía la ficha de *"Casa Amarilla (Puebla)"*, un edificio histórico de México. El monumento también aparecía en la lista de recomendaciones pese a que la información disponible era de otro país.
*   **Causa Raíz:** Todas las búsquedas a Wikipedia se realizaban únicamente con el nombre del monumento (`"Casa Puebla"`), sin ningún contexto geográfico. Al existir la palabra *"Puebla"* tanto en el nombre buscado como en el título del artículo mexicano, `difflib.get_close_matches` superaba el umbral de similitud del 30% y daba el resultado como válido. El buscador de Wikipedia, sin contexto de país, priorizaba el artículo más completo a nivel global (el de México).
*   **Solución Aplicada:** Se ha enriquecido con la ciudad activa del slot todas las consultas a Wikipedia en tres puntos del código:
    1.  **`tiene_info_wikipedia()`** — Acepta ahora un parámetro opcional `ciudad`. Si se proporciona, construye la query como `"{nombre} {ciudad}"` (ej: `"Casa Puebla Badajoz"`), forzando al buscador a priorizar resultados geográficamente relevantes.
    2.  **`ActionBuscarMonumentos`** — Pasa `ciudad=ciudad` al llamar a `tiene_info_wikipedia()`, de forma que el filtrado previo de la lista ya excluye monumentos sin artículo en el contexto geográfico correcto.
    3.  **`ActionInfoMonumento`** — Lee el slot `ciudad` y construye `query_wiki` con contexto antes de llamar a `buscar_en_wikipedia()`. Este `query_wiki` también se usa en el fallback multilingüe (inglés → español) para mantener la coherencia geográfica en ambas búsquedas.
*   **Efecto:** `"Casa Puebla Badajoz"` no devuelve resultado en Wikipedia (el edificio no tiene artículo propio), por lo que el bot ya no lo incluye en la lista de recomendaciones ni intenta mostrar información sobre él, comportamiento honesto y correcto.

## 13. Listado de Eventos Sin Fecha ni Precio
*   **Problema Detectado:** La respuesta de `ActionBuscarEventos` mostraba solo el nombre del evento y un enlace de compra, sin indicar cuándo se celebra ni cuánto cuestan las entradas. Esto obligaba al usuario a abrir cada enlace para obtener información básica, degradando la experiencia.
*   **Causa Raíz:** El bucle de formateo de eventos solo extraía los campos `name` y `url` de la respuesta de Ticketmaster, ignorando los campos `dates.start` y `priceRanges` que la API ya devuelve.
*   **Solución Aplicada:** Se amplió el bucle de `ActionBuscarEventos` en `actions.py` para extraer y formatear tres campos adicionales por evento:
    *   **Fecha y hora** — Se lee `dates.start.localDate` (ej: `"2025-06-14"`) y `dates.start.localTime` (ej: `"20:00:00"`) y se reformatean como `"14/06/2025 20:00h"`.
    *   **Rango de precio** — Se lee `priceRanges[0]` y se formatea como `"25–80 EUR"` si hay rango, o `"desde 25 EUR"` si solo hay precio mínimo.
    *   **Composición dinámica** — Cada campo es opcional: si Ticketmaster no lo incluye (precio TBD, eventos sin hora fija), se omite silenciosamente sin romper el formato.
*   **Formato resultante:**
    ```
    - **Museo Banksy Madrid** · 📅 15/05/2025 20:00h · 🎟 12–25 EUR (Entradas)
    - **Bad Bunny** · 📅 22/06/2025 21:00h · 🎟 desde 89 EUR (Entradas)
    ```
