# Manual rápido: consultas a Wikipedia en ThothBot

Este manual explica cómo funciona la consulta a Wikipedia para información de monumentos, el sistema de soporte bilingüe y cómo diagnosticar fallos.

---

## 1. Flujo Bilingüe y Fallback

ThothBot detecta el idioma del usuario y prioriza la información en ese idioma. Sin embargo, muchos monumentos españoles no tienen artículo en la Wikipedia en inglés.

### Proceso de decisión:
1. **Detección:** Se identifica el idioma (`es` o `en`).
2. **Búsqueda Primaria:** Se busca en la Wikipedia del idioma detectado.
3. **Fallback (EN → ES):** Si el usuario habla inglés y no se encuentra el monumento en `en.wikipedia.org`, el sistema realiza una segunda búsqueda en `es.wikipedia.org`.
4. **Traducción Automática:** Si se usa el fallback (resultado en español para usuario inglés), el sistema traduce el resumen automáticamente.

---

## 2. Sistema de Traducción (MyMemory API)

Para garantizar que un usuario de habla inglesa reciba la información en su idioma incluso si el artículo solo existe en español, ThothBot integra la **API de MyMemory**.

### Función `traducir_es_en(texto)`
- **Proveedor:** MyMemory (Translated.net).
- **Endpoint:** `https://api.mymemory.translated.net/get`
- **Funcionamiento:** Envía el texto en español con el parámetro `langpair=es|en`.
- **Resiliencia:** Si la API falla o se supera el límite de cuota, la función devuelve el texto original en español mediante un bloque `try-except` para evitar que el bot se detenga.

---

## 3. Detalles Técnicos de Consulta

### Búsqueda de Títulos (`buscar_en_wikipedia`)
- **Endpoint:** `https://{idioma}.wikipedia.org/w/api.php`
- **Parámetros:** `action=query`, `list=search`, `srsearch=<texto>`, `srlimit=1`

### Obtención de Resumen (`obtener_resumen_wikipedia`)
- **Endpoint:** `https://{idioma}.wikipedia.org/api/rest_v1/page/summary/<titulo>`
- **Parámetros adicionales:** `idioma_ui` (define en qué idioma se muestran las etiquetas fijas como "More info:").

---

## 4. Punto crítico: User-Agent

Wikipedia bloquea peticiones sin un `User-Agent` descriptivo. **Obligatorio** en todas las funciones:
- **Valor:** `ThothBot/1.0 (proyecto TFG)`

---

## 5. Errores típicos y diagnóstico

| Error | Causa | Solución |
|-------|-------|----------|
| `No encontré información fiable...` | Sin título válido o artículo inexistente | Refinar nombre o comprobar en navegador |
| `403 Forbidden` | Falta `User-Agent` | Revisar cabeceras en `actions.py` |
| Resumen en español para usuario inglés | Fallo en MyMemory API | Comprobar conexión a internet o cuota de MyMemory |
| `oro` en lugar de `Torre del Oro` | Extracción parcial del NLU | El sistema ahora incluye un fallback que prioriza la frase completa si el NLU corta el nombre |

---

## Ubicación del código
- `actions/actions.py`:
  - `buscar_en_wikipedia`: Lógica de búsqueda.
  - `obtener_resumen_wikipedia`: Extracción de contenido y formateo.
  - `traducir_es_en`: Integración con MyMemory.
  - `ActionInfoMonumento`: Coordinación del flujo y fallback bilingüe.
