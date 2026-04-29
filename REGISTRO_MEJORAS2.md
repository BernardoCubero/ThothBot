# Registro de Mejoras — Fase 2 (ThothBot)

Este documento registra las mejoras de la segunda fase de desarrollo, centradas en personalización de la experiencia de usuario y persistencia de datos.

---

## Mejora 14 — Registro de Usuario y Saludo Personalizado

### Objetivo
En lugar de responder al saludo con un mensaje genérico, el bot pedirá al nuevo usuario su **nombre**, **ciudad de origen** y **país**. Estos datos se almacenarán en **MariaDB**. En conversaciones posteriores, si el usuario ya existe en la base de datos, el bot le saludará directamente por su nombre.

### Arquitectura prevista

```
Usuario saluda
    │
    ├── ¿Existe en MariaDB? ──► SÍ ──► "¡Bienvenido de nuevo, {nombre}!"
    │
    └── NO ──► Formulario de registro
                    ├── Pedir nombre
                    ├── Pedir ciudad de origen
                    └── Pedir país
                            │
                            └── Guardar en MariaDB ──► "¡Encantado, {nombre}!"
```

### Tabla MariaDB prevista
```sql
CREATE TABLE usuarios (
  id              INT AUTO_INCREMENT PRIMARY KEY,
  conversation_id VARCHAR(255) NOT NULL UNIQUE,
  nombre          VARCHAR(100),
  ciudad_origen   VARCHAR(100),
  pais            VARCHAR(100),
  fecha_registro  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Equivalencia de campos
```
  conversation_id  → identificador único de sesión Rasa
  nombre           → nombre del usuario
  ciudad_origen    → ciudad donde vive el usuario
  pais             → país de origen
  fecha_registro   → insertada automáticamente por MariaDB
```

<!-- eliminado bloque json anterior (era MongoDB) -->
  "ciudad_origen": "Viena",
  "pais": "Austria",
  "fecha_registro": "2026-04-29T19:30:00"
}
```

---

## Plan de implementación paso a paso

### ✅ PASO 1 — Crear la capa de datos con SQLAlchemy ORM ✔️ COMPLETADO
- **ORM elegido:** SQLAlchemy (ya presente en el entorno de Rasa, sin dependencias nuevas salvo PyMySQL)
- **`actions/db/models.py`** — Define la clase `Usuario` con `declarative_base`. La tabla se crea automáticamente al importar `user_store.py`.
- **`actions/db/user_store.py`** — Lee credenciales de `.env`, crea engine + sesión, y expone:
  - `guardar_usuario(conversation_id, nombre, ciudad_origen, pais)` — upsert
  - `buscar_usuario(conversation_id)` — devuelve objeto `Usuario` o `None`
- **Variables `.env` necesarias:** `MARIADB_USER`, `MARIADB_PASSWORD`, `MARIADB_HOST`, `MARIADB_PORT`, `MARIADB_DB`
- Crear un nuevo archivo `actions/db/user_store.py`
- Implementar dos funciones:
  - `guardar_usuario(conversation_id, nombre, ciudad_origen, pais)` — inserta o actualiza
  - `buscar_usuario(conversation_id)` — devuelve el documento si existe, None si no

### ✅ PASO 2 — Añadir slots en `domain.yml`
- `nombre_usuario` (type: text)
- `ciudad_origen` (type: text)
- `pais_usuario` (type: text)

### ✅ PASO 3 — Crear el formulario en `domain.yml`
- Formulario `registro_usuario_form` que rellena los tres slots anteriores
- Añadir los `utter_ask_*` correspondientes para cada pregunta

### ✅ PASO 4 — Añadir intents y ejemplos en `data/nlu.yml`
- Los intents de nombre, ciudad y país ya los captura el motor de entidades de Rasa (free-text slots), no hace falta intent específico

### ✅ PASO 5 — Crear `ActionRegistrarUsuario` en `actions/actions.py`
- Lee los tres slots del form
- Llama a `guardar_usuario()` de `user_store.py`
- Responde con "¡Encantado, {nombre}! ¿En qué puedo ayudarte?"

### ✅ PASO 6 — Crear `ActionSaludoPersonalizado` en `actions/actions.py`
- Lee el `conversation_id` del tracker
- Llama a `buscar_usuario(conversation_id)`
- Si existe → saluda por nombre y salta el form
- Si no existe → activa `registro_usuario_form`

### ✅ PASO 7 — Actualizar `data/rules.yml`
- Regla: intent `saludo` → `ActionSaludoPersonalizado`
- Regla: form completado → `ActionRegistrarUsuario`

### ✅ PASO 8 — Actualizar `domain.yml`
- Registrar las dos nuevas acciones
- Registrar el formulario

### ✅ PASO 9 — Reentrenar el modelo
- `rasa train`

### ✅ PASO 10 — Probar
- Primera conversación: debe pedir nombre, ciudad, país y guardar en Mongo
- Segunda conversación (mismo conversation_id): debe saludar directamente por nombre

---

## Estado actual

| Paso | Estado |
|------|--------|
| 1 — `user_store.py` | ⬜ Pendiente |
| 2 — Slots en domain.yml | ⬜ Pendiente |
| 3 — Formulario en domain.yml | ⬜ Pendiente |
| 4 — NLU | ⬜ Pendiente |
| 5 — ActionRegistrarUsuario | ⬜ Pendiente |
| 6 — ActionSaludoPersonalizado | ⬜ Pendiente |
| 7 — rules.yml | ⬜ Pendiente |
| 8 — domain.yml (acciones) | ⬜ Pendiente |
| 9 — rasa train | ⬜ Pendiente |
| 10 — Test | ⬜ Pendiente |
