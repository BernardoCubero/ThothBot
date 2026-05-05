# Registro de Mejoras — Fase 3 (ThothBot)

Este documento registra los errores detectados durante la sesión de pruebas del **05/05/2026** (fichero `error1.txt`) y las soluciones aplicadas en `actions/actions.py` y `domain.yml`.

> **Actualización 05/05/2026 (sesión 2):** Se añaden las Mejoras 21 y 22 detectadas durante las pruebas en vivo del bot tras aplicar las mejoras 15-20.

---

## Mejora 21 — Páginas de Desambiguación de Wikipedia Devueltas Como Respuesta Válida

### Problema Detectado
Al preguntar por `"informacion sobre parc guel"` (o `"parc güel"`, `"el parque guel"`), el bot devolvía la ficha de **Güell** (una página de desambiguación de Wikipedia sobre el apellido catalán), en lugar de la información del Parc Güell o un "no encontrado" honesto.

La respuesta errónea era:
> *Güell — página de desambiguación de Wikimedia*
> *Güell es un apellido histórico español muy presente arraigado históricamente en Cataluña...*

### Causa Raíz
Dos causas combinadas:

1. **La API REST de Wikipedia devuelve páginas de desambiguación como resultados válidos.** Estas páginas tienen `type: "disambiguation"` en el JSON de respuesta, pero el código no comprobaba ese campo y devolvía el contenido sin filtrar.

2. **El cutoff de `get_close_matches` se superaba incorrectamente.** La consulta `"parc guel"` comparada con `"Güell"` (normalizado a `"guell"`) produce una ratio de SequenceMatcher de ~0.57 (> 0.5), porque la subcadena `"guel"` aparece en ambos textos. El sistema lo aceptaba como válido cuando no lo era.

### Por Qué el Nombre Era "Güell" y No "Parc Güell"
Cuando Wikipedia busca `"parc guel barcelona"`, el motor de búsqueda prioriza el artículo de desambiguación `"Güell"` porque contiene todas las palabras clave. El artículo real `"Parc Güell"` solo aparecería si se busca exactamente con ese nombre acentuado.

### Solución Aplicada

**1. En `obtener_resumen_wikipedia()`** — Detección y rechazo de disambiguation pages antes de construir la respuesta:

```python
# CAMBIO: Rechazar páginas de desambiguación de Wikipedia.
tipo_pagina = data.get("type", "")
descripcion = data.get("description", "")
terminos_disambig = ["desambiguación", "disambiguation", "wikimedia disambiguation"]
if tipo_pagina == "disambiguation" or any(t in descripcion.lower() for t in terminos_disambig):
    print(f"[Wikipedia] Rechazada página de desambiguación: '{data.get('title', titulo)}'")
    return None
```

La API REST de Wikipedia incluye el campo `type` con el valor `"disambiguation"` para estas páginas. También se comprueba la descripción como segundo mecanismo de seguridad.

**2. En `tiene_info_wikipedia()`** — También se descarta la desambiguación en el filtrado previo de la lista de monumentos:

```python
# opensearch devuelve [query, [titulos], [descripciones], [urls]]
descripciones = data[2] if len(data) > 2 else []
if titulos:
    descripcion_resultado = descripciones[0].lower() if descripciones else ""
    terminos_disambig = ["desambiguación", "disambiguation"]
    if any(t in descripcion_resultado for t in terminos_disambig):
        return False  # No incluir en la lista de monumentos
```

### Resultado
Ahora, al buscar `"parc guel"`:
- `obtener_resumen_wikipedia("Güell")` → detecta `type="disambiguation"` → devuelve `None`
- El bot responde con el mensaje de "no encontrado" + consejo de reformulación
- El Parc Güell **sí** aparece en la lista de monumentos de Barcelona (tiene tag wikidata en Geoapify), por lo que el usuario puede pedirlo explícitamente escribiendo `"Parc Güell"` con el nombre correcto

### Lección Aprendida
La API REST de Wikipedia siempre incluye el campo `type` en su respuesta. Antes de mostrar cualquier información al usuario, es obligatorio comprobar que `type == "standard"`. Las páginas `"disambiguation"` y `"no-extract"` nunca deben mostrarse como respuesta directa. Este campo debe comprobarse en **todos** los puntos donde se consume la API de Wikipedia.

### Tarea Futura
- **[ ]** Cuando se rechaza una disambiguation page, intentar una búsqueda secundaria añadiendo el nombre de la ciudad al título (ej: `"Parc Güell Barcelona"`) antes de devolver "no encontrado".

---

---

## Mejora 15 — Validación de Entradas Numéricas Puras

### Problema Detectado
Al introducir un dígito o número solo (ej: `3`, `123`, `2026`), el bot procesaba el valor como si fuera un nombre de ciudad o monumento, devolviendo respuestas incoherentes como intentar buscar una ciudad llamada `"3"` en Geoapify.

### Causa Raíz
No existía ninguna validación de entrada en las acciones. El código de extracción de ciudad por "última palabra" cogía cualquier token del mensaje sin distinguir si era texto o un número. Geoapify intentaba geocodificar `"3, Spain"` y devolvía coordenadas erróneas o directamente fallaba silenciosamente.

### Solución Aplicada
Se creó la función auxiliar `es_solo_numeros(texto)` en `actions.py`:

```python
def es_solo_numeros(texto):
    """Devuelve True si el texto es un número puro (ej: '123', '3')."""
    return texto.strip().lstrip('+-').replace('.', '', 1).isdigit()
```

Esta función se aplica como **guard clause al inicio** de las tres acciones principales:

- **`ActionBuscarMonumentos`** → devuelve `ciudad_no_encontrada` con el número como ciudad.
- **`ActionBuscarEventos`** → devuelve `pedir_ciudad` para que el usuario especifique una ciudad real.
- **`ActionInfoMonumento`** → devuelve `pedir_monumento` para que el usuario reformule.

Además, se protegen los **fallbacks de extracción de última palabra** para que nunca usen un token numérico como candidato a ciudad, evitando la propagación del error:

```python
if not es_solo_numeros(candidata) and len(candidata) >= 2:
    ciudad = candidata
```

### Lección Aprendida
Siempre validar el tipo de dato de la entrada del usuario antes de enviarlo a una API externa. Los servicios de geocodificación no están diseñados para recibir números y pueden devolver resultados que parecen válidos pero son completamente incorrectos.

---

## Mejora 16 — Corrección del Fallo "visit barcelona" (Inglés sin Keyword)

### Problema Detectado
La frase `"visit barcelona"` en inglés devolvía:
> *"Hubo un problema al consultar los monumentos."*

Mientras que `"monuments in barcelona"` funcionaba correctamente.

### Causa Raíz
El método `.lower()` se aplicaba sobre el resultado de `.get("text")` directamente, sin proteger el caso `None`. Si el tracker devolvía `None` en algún punto, se producía un `AttributeError` silencioso capturado por el `except Exception` general, que disparaba el mensaje de error genérico de la API.

Adicionalmente, el detector de intenciones de monumento solo buscaba palabras como `"castle"`, `"cathedral"`, etc., pero no frases de información en inglés como `"information about"`, `"tell me about"` o `"info about"`. Estas frases llegaban a `ActionBuscarMonumentos` en lugar de redirigirse a `ActionInfoMonumento`.

### Solución Aplicada
1. **Protección contra `None`** — Se cambió `tracker.latest_message.get("text").lower()` por el patrón seguro:
   ```python
   mensaje = tracker.latest_message.get("text") or ""
   idioma = detectar_idioma(mensaje.lower())
   ```

2. **Ampliación de keywords de detección** — Se añadieron tres nuevas frases al detector:
   ```python
   "information about",
   "info about",
   "tell me about",
   ```

### Lección Aprendida
Nunca encadenar `.lower()` u otros métodos directamente sobre un `.get()` sin proteger el `None`. Usar siempre el patrón `or ""` como valor por defecto. También es importante mantener sincronizadas las keywords de detección de idioma/intención con los patrones reales de uso del usuario.

---

## Mejora 17 — Falso Positivo "Palau Robert → Palau Blaugrana"

### Problema Detectado
Al preguntar `"information about palau robert"`, el bot devolvía la ficha del **Palau Blaugrana** (pabellón del FC Barcelona), un edificio completamente distinto, en lugar de devolver un "no encontrado" honesto.

### Causa Raíz
El umbral de similitud de `get_close_matches` estaba configurado en `cutoff=0.3` (30%). Esto era demasiado permisivo: las palabras `"palau"` y `"blaugrana"` comparten suficiente similitud léxica con `"palau robert"` para superar ese umbral mínimo. El bot aceptaba el resultado como válido cuando no lo era.

### Solución Aplicada
Se subió el umbral de similitud de **0.3 a 0.5** en los dos puntos del código donde se usa:

```python
# Validación principal
if titulo and not get_close_matches(monumento.lower(), [titulo.lower()], cutoff=0.5):
    titulo = None

# Fallback EN → ES
if titulo_es and get_close_matches(monumento.lower(), [titulo_es.lower()], cutoff=0.5):
```

Con `cutoff=0.5`, `"palau robert"` vs `"palau blaugrana"` ya no supera el umbral y el bot devuelve correctamente el mensaje de "no encontrado".

### Lección Aprendida
Un umbral de similitud bajo en `difflib` actúa como un filtro poroso que deja pasar falsos positivos. Para nombres propios compuestos (dos palabras), si solo una coincide, el 30% puede ser suficiente para engañar al sistema. El 50% es un punto de equilibrio mejor para este caso de uso: descarta falsos positivos sin ser tan estricto que rechace monumentos con pequeñas variaciones ortográficas.

> **Referencia:** Ver también Mejora 7 (donde se implementó por primera vez el cutoff=0.3) y Mejora 12 (enriquecimiento con ciudad para desambiguación geográfica).

---

## Mejora 18 — Extracción Incorrecta con Typo y Artículos ("Alcazabar de badajoz")

### Problema Detectado
La consulta `"Dime informacion del Alcazabar de badajoz"` (con typo: *Alcazabar* en lugar de *Alcazaba*) devolvía:
> *No encontré información fiable sobre 'del alcazabar badajoz'.*

El nombre incluía incorrectamente el artículo `"del"` en la consulta a Wikipedia.

### Causa Raíz
La lista de `stopwords_es` en `i18n_config.json` no incluía `"del"` como palabra a eliminar. Al procesar la frase completa en modo fallback, la palabra `"del"` quedaba incluida en la query enviada a Wikipedia, reduciendo la probabilidad de encontrar el artículo correcto.

Adicionalmente, el typo `"alcazabar"` (en lugar de `"alcazaba"`) hacía que `get_close_matches` con cutoff=0.5 rechazara el artículo correcto de Wikipedia (que sí existe como *"Alcazaba de Badajoz"*). Este es el comportamiento esperado tras la Mejora 17, pero evidencia la necesidad de mejorar la tolerancia a typos de cara a futuras iteraciones.

### Solución Aplicada
Se añadió `"del"` a la lista de `stopwords_es` en `i18n_config.json` y `"del"` ya estaba en `stopwords_en`. También se añadió `"del"` a la lista de `prefijos` en `action_info_monumento` para que se elimine como prefijo del nombre normalizado:

```json
"prefijos": ["la ", "el ", "los ", "las ", "the ", "a ", "an ", "del "]
```

> **Estado parcial:** Con el typo *"alcazabar"* el sistema no puede encontrar el artículo correcto incluso tras limpiar stopwords — este comportamiento es técnicamente correcto con el cutoff=0.5. Una mejora futura podría implementar corrección ortográfica previa a la búsqueda.

### Lección Aprendida
Los artículos contractos (`del`, `al`) son igual de problemáticos que los simples (`de`, `la`) y deben estar en las stopwords. Los typos son un problema abierto que requiere una capa de corrección ortográfica (ej. `pyspellchecker` o la API `spell` de Wikipedia) para ser resuelto de forma robusta.

### Tarea Futura
- **[ ]** Implementar corrección ortográfica previa a la búsqueda de monumentos (ej. con `pyspellchecker`).
- **[ ]** Considerar el uso del endpoint `spell` de la Wikipedia API como alternativa.

---

## Mejora 19 — Intent "bot_challenge" No Definido en Domain

### Problema Detectado
Al ejecutar el bot, la consola mostraba repetidamente el siguiente aviso en amarillo:

```
UserWarning: Parsed an intent 'bot_challenge' which is not defined in the domain.
Please make sure all intents are listed in the domain.
More info at https://rasa.com/docs/rasa/domain
```

### Causa Raíz
El archivo `data/nlu.yml` contenía ejemplos de entrenamiento para el intent `bot_challenge` (preguntas del tipo *"are you a bot?"*), pero dicho intent no estaba declarado en `domain.yml`. Rasa lo reconoce en los mensajes de usuario pero no sabe qué hacer con él, generando el aviso en cada invocación.

### Solución Aplicada
Se añadió `bot_challenge` a la lista de intents de `domain.yml`:

```yaml
intents:
  - ...
  - bot_challenge
```

Se añadió también la respuesta `utter_bot_challenge` con versiones en español e inglés:

```yaml
utter_bot_challenge:
  - text: "Soy ThothBot, un asistente virtual. ¡No soy humano! 😊"
  - text: "I'm ThothBot, a virtual assistant — not a human! 😊"
```

### Lección Aprendida
Cualquier intent declarado en `nlu.yml` debe estar **siempre** también declarado en `domain.yml`. Después de añadir nuevos ejemplos de entrenamiento NLU, revisar que el domain esté sincronizado antes de ejecutar `rasa train`.

---

## Mejora 20 — Input Vacío o Demasiado Corto Sin Respuesta

### Problema Detectado
El log `error1.txt` terminaba con un input vacío (`Your input ->`), y la sesión final con `"I am im"` (input incompleto) provocaba que el bot respondiera en español con recomendaciones de Córdoba, resultado de un contexto de sesión mal resuelto.

### Causa Raíz
`ActionInfoMonumento` llamaba directamente a `.lower()` sobre el texto del mensaje sin comprobar si estaba vacío o era demasiado corto para ser una búsqueda válida. Inputs de 1-2 caracteres (ej: `"im"`, `"I"`) superaban la validación mínima de `len < 3` que solo comprobaba el slot del monumento, no el texto completo del mensaje.

### Solución Aplicada
Se añadió un **guard clause al inicio** de `ActionInfoMonumento` que rechaza explícitamente los mensajes vacíos o de longitud inferior a 2 caracteres:

```python
mensaje_raw = tracker.latest_message.get("text") or ""
mensaje = mensaje_raw.lower()
idioma = detectar_idioma(mensaje)

# Rechazar entradas puramente numéricas o demasiado cortas
if es_solo_numeros(mensaje_raw.strip()) or len(mensaje_raw.strip()) < 2:
    dispatcher.utter_message(text=TEXTOS["action_info_monumento"]["respuestas"][idioma]["pedir_monumento"])
    return []
```

### Lección Aprendida
El input del usuario nunca debe darse por garantizado. Cualquier acción que procese texto debe validar mínimamente que existe, que no es vacío y que tiene longitud suficiente para ser procesado antes de enviarlo a APIs externas.

---

---

## Mejora 23 — Persistencia Errónea del Slot Ciudad ("Mila") al Cambiar de Intent

### Problema Detectado
Tras consultar información sobre la Casa Milà, el usuario preguntó `"que eventos hay en barcelona"`, pero el bot respondió:
> *"No tengo eventos próximos para Mila en este momento."*

Incluso repitiendo la palabra `"eventos"`, el bot seguía buscando en la ciudad "Mila".

### Causa Raíz
El problema era una cadena de tres factores:
1. Al preguntar por Casa Milà, el NLU de Rasa extrajo `"Mila"` como entidad `ciudad` en lugar de (o además de) `monumento`, sobreescribiendo el slot `ciudad` con `"Mila"`.
2. Al preguntar `"que eventos hay en barcelona"`, el NLU no logró extraer `"barcelona"` como entidad `ciudad` (posiblemente por falta de ejemplos de entrenamiento con esa estructura exacta para el intent `buscar_eventos`).
3. El código de `ActionBuscarEventos` y `ActionRecomendarPlanes` tenía un bloque de *fallback* para extraer la ciudad de la última palabra del mensaje, pero **solo se ejecutaba si el slot `ciudad` estaba vacío**. Como el slot ya contenía `"Mila"`, el fallback se ignoraba y el bot buscaba eventos en "Mila".

Adicionalmente, al aplicar el mismo fallback unificado de `ActionBuscarMonumentos` (donde sí sobreescribe el slot si la última palabra es diferente), se descubrió un nuevo problema: si el usuario decía solo `"eventos"`, la última palabra era "eventos", diferente de la ciudad actual, por lo que el bot sustituía la ciudad por "eventos" y buscaba en un lugar llamado "Eventos" (o "Monumentos").

### Solución Aplicada
1. **Unificación del Fallback:** Se copió la lógica avanzada de fallback de `ActionBuscarMonumentos` a `ActionBuscarEventos` y `ActionRecomendarPlanes`. Ahora, incluso si el slot `ciudad` tiene un valor previo (ej. `"Mila"`), se evalúa la última palabra del mensaje (ej. `"barcelona"`). Si es válida y diferente, se actualiza el slot.
2. **Lista Negra de Palabras Clave:** Se añadió un filtro `palabras_ignoradas` en el fallback de las 3 acciones para evitar que comandos sueltos (como `"eventos"`, `"monumentos"`, `"planes"`) sobrescriban la ciudad actual:
   ```python
   palabras_ignoradas = [
       "monumentos", "ver", "visitar", "sitios", "lugares", "informacion",
       "eventos", "conciertos", "teatro", "deporte", "partido", "festival",
       "musica", "actividades", "planes", "recomendaciones", "sugerencias"
   ]
   if candidata not in palabras_ignoradas ... :
       ciudad = candidata
   ```
3. **Limpieza de Puntuación:** Se añadió `.rstrip(".,!?")` para limpiar posibles signos de puntuación pegados a la ciudad (ej: `"barcelona?"`).

### Lección Aprendida
Cuando se confía en *fallbacks* heurísticos (como "tomar la última palabra como ciudad"), hay que protegerlos contra entradas de un solo token que representen la intención (ej: "eventos"). Además, el comportamiento de sobreescritura de slots debe ser consistente en todas las acciones del bot para permitir transiciones fluidas de una ciudad a otra o de un intent a otro.

---

## Resumen de Cambios de Esta Sesión (05/05/2026)

| # | Fichero | Cambio |
|---|---------|--------|
| 15 | `actions/actions.py` | Nueva función `es_solo_numeros()` + guards en 3 acciones |
| 16 | `actions/actions.py` | Protección `or ""` en `.get("text")` + keywords EN ampliadas |
| 17 | `actions/actions.py` | Cutoff `get_close_matches` subido 0.3 → 0.5 |
| 18 | `data/i18n_config.json` | `"del"` añadido a stopwords y prefijos |
| 19 | `domain.yml` | Intent `bot_challenge` + `utter_bot_challenge` añadidos |
| 20 | `actions/actions.py` | Guard clause input vacío/corto en `ActionInfoMonumento` |
| 21 | `actions/actions.py` | Detección y rechazo de páginas de desambiguación de Wikipedia |
| 22 | `actions/actions.py` | Eliminación de "ciudad" en query de opensearch que provocaba resultados nulos |
| 23 | `actions/actions.py` | Fallback de extracción de ciudad unificado e ignora palabras clave del intent |

---

## Tareas Pendientes Identificadas Esta Sesión

- **[ ]** Implementar corrección ortográfica previa a Wikipedia (typos como *"alcazabar"*).
- **[ ]** Separar intents `saludo` / `saludo_en` y `despedida` / `despedida_en` (pendiente desde Mejora 6, documentado en `REGISTRO_MEJORAS.md` sección "Pendiente Fase 2").
- **[ ]** Continuar Mejora 14 — Registro de usuario personalizado con MariaDB (pendiente en `REGISTRO_MEJORAS2.md`).
- **[ ]** Añadir ejemplos `"visit {ciudad}"` y `"I am in {ciudad}"` al NLU para mejorar la cobertura de intents en inglés.
