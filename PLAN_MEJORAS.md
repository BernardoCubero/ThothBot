# Plan de Acción — Mejoras Post-Despliegue ThothBot
**Fecha:** 2026-05-12  
**Estado:** Pendiente de implementar  
**Prioridad:** Alta (antes de la defensa del TFG)

---

## 🔍 Diagnóstico completo

### Problema 1 — Monumentos poco relevantes / sin Wikipedia siguen apareciendo

**Síntoma observado:**  
Para Córdoba se muestran: Molino de Martos, Baños de la Pescadería, Estatua al Gran Capitán... pero NO aparecen la Mezquita-Catedral, el Alcázar de los Reyes Cristianos, el Puente Romano, etc.

**Causa raíz (doble):**

**A) Geoapify devuelve hasta 10 POIs sin ranking de relevancia:**  
La query actual (`categories: tourism.sights`, `limit: 10`, `filter: circle:5000m`) devuelve POIs ordenados por distancia al centroide de la ciudad, no por importancia turística. Los monumentos más famosos pueden estar geográficamente más lejos del centroide que estatuas menores.

```python
# Código actual (actions.py línea 344-349)
params = {
    "categories": "tourism.sights",
    "filter": f"circle:{lon},{lat},5000",
    "limit": 10,   # ← solo 10, sin criterio de relevancia
    "apiKey": API_KEY,
}
```

**B) `tiene_info_wikipedia()` con cutoff=0.3 es demasiado permisivo:**  
Un cutoff de 0.3 en `difflib.get_close_matches` acepta resultados con muy poca similitud. "Molino" podría matchear "Molinos de Papel" etc. Esto hace que monumentos sin artículo real pasen el filtro.

```python
# Código actual (actions.py línea 238)
if get_close_matches(nombre.lower(), [titulo.lower()], cutoff=0.3):  # ← demasiado bajo
    return True
```

**Además:** la flag `tiene_wikidata` (línea 367) sólo comprueba si hay un tag `wikidata` en los metadatos de Geoapify, pero NO verifica que el artículo de Wikipedia tenga contenido real y relevante. Un lugar puede tener tag Wikidata y no tener artículo Wikipedia útil.

---

### Problema 2 — Eventos muestran la URL completa en lugar de un enlace clickable

**Síntoma observado:**  
```
- **Sasha Velour - Travesty** 📅 12/06/2026 · [Entradas](https://www.ticketmaster.es/...)
```
Aparece el texto literal `[Entradas](url)` en lugar de un enlace clickable.

**Causa raíz (doble):**

**A) El proxy de Telegram no activa `parse_mode`:**  
```python
# telegram_proxy/bot.py — actual
await update.message.reply_text(msg["text"])  # ← sin parse_mode
```
Sin `parse_mode='Markdown'`, Telegram trata el texto como plano y no renderiza los links `[texto](url)`.

**B) `actions.py` usa `**bold**` (doble asterisco) que NO es Markdown de Telegram:**  
Telegram usa `*bold*` (asterisco simple). El formato `**nombre**` en Telegram se muestra literalmente.

```python
# actions.py línea 510 — actual
linea = f"- **{nombre}**"  # ← doble asterisco, no funciona en Telegram
```

---

### Problema 3 — Formato Markdown roto en monumentos también

El mismo problema de `parse_mode` afecta a `action_info_monumento` que genera respuestas con `*Título*`, `_descripción_` y links. Sin parse_mode activo, todo se muestra como texto plano.

---

## 📋 Plan de acción detallado

---

### TAREA 1 — Arreglar el proxy de Telegram (parse_mode)
**Fichero:** `telegram_proxy/bot.py`  
**Prioridad:** 🔴 Crítica  
**Esfuerzo:** Bajo (5 min)

**Cambios:**
1. Añadir `parse_mode='Markdown'` en `reply_text()`
2. Añadir función `convertir_markdown()` que transforma `**texto**` → `*texto*` antes de enviar

```python
# Función a añadir
def convertir_markdown(texto):
    """Convierte markdown de GitHub/Slack a Telegram Markdown."""
    import re
    # **bold** → *bold*
    texto = re.sub(r'\*\*(.+?)\*\*', r'*\1*', texto)
    return texto

# En _send_to_rasa_and_reply:
await update.message.reply_text(
    convertir_markdown(msg["text"]),
    parse_mode='Markdown'
)
```

**Cuidado:** Telegram Markdown v1 tiene caracteres reservados. Si el texto tiene `_`, `*`, `[`, `` ` `` fuera de formato, puede romper el parse. Usar `disable_web_page_preview=True` para evitar previews largos.

---

### TAREA 2 — Mejorar calidad de monumentos (Geoapify + Wikipedia)
**Fichero:** `actions/actions.py`  
**Prioridad:** 🔴 Crítica  
**Esfuerzo:** Medio (30-45 min)

**Cambios:**

**2A — Subir el limit de Geoapify y añadir condición de `wikidata` obligatorio como primer filtro:**
```python
params = {
    "categories": "tourism.sights,tourism.attraction",  # más categorías
    "filter": f"circle:{lon},{lat},8000",               # radio más amplio
    "limit": 20,                                         # más candidatos
    "apiKey": API_KEY,
}
```

**2B — Cambiar la lógica de filtrado: priorizar lugares con tag Wikidata, luego validar con Wikipedia:**

La nueva lógica debe ser:
1. **Nivel 1 (preferido):** lugar tiene tag `wikidata` en Geoapify → incluirlo directamente, es un lugar conocido
2. **Nivel 2 (fallback):** no tiene wikidata tag → verificar con `tiene_info_wikipedia()` con **cutoff elevado a 0.5**
3. Si no pasa ningún nivel → descartar

```python
# Nueva lógica de filtrado
PRIORIDAD_WIKIDATA = []
CANDIDATOS_WIKI = []

for lugar in data.get("features", []):
    props = lugar.get("properties", {})
    nombre = props.get("name")
    if not nombre:
        continue
    
    raw = props.get("datasource", {}).get("raw", {})
    tiene_wikidata = bool(raw.get("wikidata") or raw.get("wikipedia"))
    
    if tiene_wikidata:
        PRIORIDAD_WIKIDATA.append(nombre)
    elif tiene_info_wikipedia(nombre, idioma, ciudad=ciudad):
        CANDIDATOS_WIKI.append(nombre)

# Primero los que tienen wikidata, luego los validados via wikipedia
lugares = PRIORIDAD_WIKIDATA + CANDIDATOS_WIKI
lugares = lugares[:8]  # máximo 8 resultados
```

**2C — Aumentar cutoff en `tiene_info_wikipedia` de 0.3 a 0.5:**
```python
# Línea 238 — cambiar cutoff
if get_close_matches(nombre.lower(), [titulo.lower()], cutoff=0.5):  # era 0.3
    return True
```

---

### TAREA 3 — Cambiar formato de eventos (no mostrar URL, mostrar botón)
**Fichero:** `actions/actions.py`  
**Prioridad:** 🟡 Alta  
**Esfuerzo:** Bajo (10 min)

El formato actual pone la URL completa en el texto. Con parse_mode activo se verá como enlace clickable, pero sigue siendo texto largo.

**Opción A (simple):** Eliminar la URL del texto y dejarla solo como "[Entradas]":
```python
# Actual (línea 516)
linea += f" · [{enlace_texto}]({url_evento})"

# Sin cambios en actions.py — se arregla solo con parse_mode en el proxy
# El [Entradas](url) se verá como enlace clickable con parse_mode=Markdown
```

**Opción B (mejor UX):** El proxy de Telegram puede detectar si el mensaje tiene links y enviarlos como `InlineKeyboardButton`:
```python
# En el proxy: detectar links Markdown y convertir a botones de Telegram
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def extraer_botones(texto):
    patron = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
    botones = []
    for match in re.finditer(patron, texto):
        label, url = match.group(1), match.group(2)
        botones.append([InlineKeyboardButton(label, url=url)])
    texto_limpio = re.sub(patron, '', texto).strip()
    return texto_limpio, botones

# Al enviar:
texto_limpio, botones = extraer_botones(msg["text"])
reply_markup = InlineKeyboardMarkup(botones) if botones else None
await update.message.reply_text(
    convertir_markdown(texto_limpio),
    parse_mode='Markdown',
    reply_markup=reply_markup,
    disable_web_page_preview=True
)
```

> **Recomendación:** Implementar la Opción B — es más elegante y apropiada para Telegram. Los botones de "Entradas" debajo de cada evento son una UX mucho mejor que un link en el texto.

---

### TAREA 4 — Sincronizar cambios con el VPS
**Prioridad:** 🟡 Alta  
**Esfuerzo:** Bajo (5 min por cambio)

Después de cada modificación en local:

```bash
# Cambios en actions/actions.py → reiniciar action_server
scp -P 2224 /home/bernie/proyectos/ThothBot/actions/actions.py bernie@135.125.101.196:~/ThothBot/actions/
ssh -p 2224 bernie@135.125.101.196 "cd ~/ThothBot && sudo docker compose restart action_server"

# Cambios en telegram_proxy/bot.py → rebuild y restart
scp -P 2224 /home/bernie/proyectos/ThothBot/telegram_proxy/bot.py bernie@135.125.101.196:~/ThothBot/telegram_proxy/
ssh -p 2224 bernie@135.125.101.196 "cd ~/ThothBot && sudo docker compose build telegram_proxy && sudo docker compose up -d telegram_proxy"
```

---

## 🗓 Orden de implementación recomendado

> Los tiempos incluyen **explicación + comprensión + implementación + prueba**.  
> Cada tarea se hace una a una, verificando en Telegram antes de pasar a la siguiente.

| # | Tarea | Impl. | Comprensión | Total | Impacto |
|---|-------|-------|-------------|-------|---------|
| 1 | Fix `parse_mode` en proxy Telegram | 10 min | 10 min | **~20 min** | 🔴 Crítico — arregla el formato de todos los mensajes |
| 2 | Botones de Entradas en eventos | 20 min | 15 min | **~35 min** | 🟠 Alto — UX mucho mejor, más profesional |
| 3 | Mejorar filtro de monumentos | 30 min | 20 min | **~50 min** | 🟠 Alto — muestra La Mezquita, Alcázar, etc. |
| 4 | Sincronizar VPS tras cada cambio | 5 min | 0 min | **~5 min** | — |

**Total estimado con comprensión: ~1h 50min**

### ¿Qué se explica en cada tarea?

**Tarea 1 — parse_mode:**  
Qué es el parse_mode de Telegram, por qué el Markdown de GitHub (`**bold**`) difiere del de Telegram (`*bold*`), y cómo el proxy actúa de "traductor" entre el formato de Rasa y el de Telegram.

**Tarea 2 — Botones de entradas:**  
Cómo funciona la `InlineKeyboardMarkup` de Telegram (botones interactivos bajo el mensaje), cómo el proxy detecta links con regex y los convierte en botones, y por qué esto es mejor UX que mostrar la URL en el texto.

**Tarea 3 — Monumentos:**  
Cómo funciona el algoritmo de filtrado actual (Geoapify → `tiene_wikidata` → `tiene_info_wikipedia`), por qué el cutoff de 0.3 en `difflib` es demasiado bajo, y cómo priorizar por relevancia (Wikidata tag = más famoso) en lugar de por proximidad geográfica.

---

## 🔮 Mejoras opcionales (post-defensa)

- [ ] Crear tabla automáticamente al iniciar el contenedor (no manual)
- [ ] Añadir comando `/ayuda` al bot de Telegram
- [ ] Añadir botones de menú persistente en Telegram (ReplyKeyboardMarkup)
- [ ] Implementar interfaz web en `https://thothbot.alcostepc.com`
- [ ] Añadir más ciudades al sistema de recomendaciones (`action_recomendar_planes`)
- [ ] Tests de regresión automatizados para las acciones
