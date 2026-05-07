# Plan de Implementación: Interfaz Gráfica y Despliegue — ThothBot

Este documento describe la hoja de ruta para dotar a ThothBot de una interfaz visual, integración con Telegram y su posterior despliegue profesional en un VPS mediante Docker.

---

## 1. Interfaz Web (Rasa Web Chat)

Para el uso en navegadores, se utilizará el componente **Rasa Webchat** (basado en Socket.io).

### Configuración en `credentials.yml`
Se debe habilitar el canal de sockets:
```yaml
socketio:
  user_message_evt: user_uttered
  bot_message_evt: bot_uttered
  session_persistence: true
```

### Integración Frontend
Creación de un archivo `index.html` simple que cargue el widget:
```html
<div id="rasa-chat-widget" data-websocket-url="http://<TU_IP_VPS>:5005"></div>
<script src="https://cdn.jsdelivr.net/npm/rasa-webchat/lib/index.js"></script>
```

---

## 2. Integración con Telegram

Telegram servirá como la interfaz móvil principal del bot.

### Pasos previos:
1. Crear el bot en [@BotFather](https://t.me/botfather) y obtener el **API TOKEN**.
2. Configurar `credentials.yml`:
   ```yaml
   telegram:
     access_token: "TU_TELEGRAM_TOKEN"
     verify: "thothbot_verify"
     webhook_url: "https://<TU_DOMINIO_VPS>/webhooks/telegram/webhook"
   ```

---

## 3. Contenerización con Docker

Para asegurar que el bot funcione igual en local que en el VPS, usaremos `docker-compose`.

### Archivos necesarios:
- **`Dockerfile`**: Para la imagen de Rasa y las dependencias (SQLAlchemy, PyMongo, etc.).
- **`docker-compose.yml`**: Para orquestar los 4 servicios:
  1. **Rasa Server** (Core + NLU).
  2. **Action Server** (Python custom actions).
  3. **MariaDB** (Usuarios).
  4. **MongoDB** (Logs).

---

## 4. Despliegue en VPS (Nginx + SSL)

Para que Telegram acepte el webhook, es obligatorio usar **HTTPS**.

### Arquitectura de red:
1. **Nginx** actuando como Proxy Inverso.
2. **Certbot (Let's Encrypt)** para obtener certificados SSL gratuitos.
3. El tráfico llega por el puerto 443 (HTTPS) y Nginx lo redirige al puerto 5005 del contenedor de Rasa.

---

## Próximos Pasos (Hoja de Ruta)

1. [ ] Crear el `Dockerfile` personalizado que incluya todas las librerías (`requests`, `pymysql`, `pymongo`, `python-dotenv`).
2. [ ] Configurar el `docker-compose.yml` vinculando los volúmenes de las bases de datos para no perder información.
3. [ ] Probar la conexión local mediante Docker antes de subir al VPS.
4. [ ] Configurar el Webhook de Telegram.

> **Nota:** Se recomienda usar una imagen base de Python ligera (slim) para optimizar el espacio en el servidor VPS.
