# Plan de Visualización de Datos — ThothBot

Este documento describe las opciones para visualizar los logs de **MongoDB** y la base de datos de usuarios de **MariaDB** de forma remota y segura.

---

## Opción A: Comandos de Administrador (Telegram)

Es la opción más rápida y segura para un acceso rápido desde el móvil.

### 1. Autenticación por `sender_id`
En las acciones personalizadas, comprobaremos si el ID del usuario coincide con el tuyo:
```python
ADMIN_ID = "TU_ID_DE_TELEGRAM"

if tracker.sender_id == ADMIN_ID:
    # Ejecutar comando administrativo
else:
    dispatcher.utter_message(text="No tienes permisos para ver estos datos.")
```

### 2. Comandos propuestos:
- **`/stats`**: Devuelve un resumen rápido (ej: "Total usuarios: 45, Logs hoy: 120").
- **`/export_users`**: El bot genera un archivo CSV con los usuarios de MariaDB y te lo envía por el chat.
- **`/last_logs`**: Muestra los últimos 10 mensajes registrados en MongoDB.

---

## Opción B: Dashboard Web (Panel de Control)

Una interfaz visual accesible por navegador.

### 1. Implementación con Flask (Python)
Podemos crear una pequeña aplicación web independiente en el mismo VPS:
- **Ruta `/admin/users`**: Muestra una tabla con los usuarios registrados en MariaDB.
- **Ruta `/admin/logs`**: Muestra una lista cronológica de los logs de MongoDB con filtros por intent o ciudad.

### 2. Seguridad
Para evitar accesos no autorizados:
- **Basic Auth:** Usuario y contraseña sencillos para entrar a la web.
- **Protección Nginx:** Solo permitir el acceso a esta ruta desde tu IP o mediante una URL secreta.

---

## Opción C: Herramientas Externas (Recomendado para desarrollo)

Si no queremos programar una interfaz desde cero, podemos desplegar herramientas de gestión junto a los contenedores:
- **Adminer / phpMyAdmin:** Para gestionar MariaDB visualmente.
- **Mongo Express:** Un visor web para MongoDB muy ligero y potente.

---

## Próximos Pasos (Hoja de Ruta)

1. [ ] Identificar tu `sender_id` de Telegram (usando un comando `/whoami`).
2. [ ] Implementar la acción `ActionAdminStats` en Rasa.
3. [ ] Añadir los contenedores de `adminer` y `mongo-express` al `docker-compose.yml` (opcional pero muy útil).
4. [ ] Crear una ruta secreta en el Action Server para descargar los datos en formato JSON.

> **Nota de Seguridad:** Nunca expongas estos datos públicamente. Si usas la opción web, el uso de HTTPS es obligatorio.
