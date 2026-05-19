# Manual: Cómo levantar ThothBot en Web y Telegram

Este manual describe los pasos exactos para configurar y levantar ThothBot de forma que responda tanto a través de la interfaz web (navegador) como a través de Telegram.

Gracias a la arquitectura basada en contenedores Docker, ambos canales (Web y Telegram) funcionarán simultáneamente comunicándose con el mismo motor de Rasa.

---

## 1. Configuración Previa

Antes de levantar los clientes, asegúrate de que el entorno base tiene todas las variables necesarias configuradas.

### Archivo `.env`
En la raíz del proyecto existe un archivo `.env` (si no existe, cópialo desde `.env.example`). Asegúrate de que las siguientes variables estén definidas:

```env
# Claves de APIs Externas
GEOAPIFY_API_KEY=tu_clave_de_geoapify
TKMASTER=tu_clave_de_ticketmaster

# Base de datos
MARIADB_USER=root
MARIADB_PASSWORD=tu_contraseña_aqui
MARIADB_HOST=db
MARIADB_PORT=3306
MARIADB_DB=thothbot_db

# MongoDB
MONGO_HOST=mongodb
MONGO_PORT=27017
MONGO_DB=thothbot

# Telegram
TOKEN_TELEGRAM=tu_token_generado_en_bot_father
```

> **Nota sobre Telegram:** Para conseguir el `TOKEN_TELEGRAM`, debes iniciar un chat con [@BotFather](https://t.me/botfather) en Telegram, usar el comando `/newbot`, seguir los pasos y copiar el **API Token** que te proporciona.

---

## 2. Levantar la Infraestructura Base (Backend)

Ambos canales requieren que el motor principal del bot, el servidor de acciones, el proxy y las bases de datos estén funcionando. Todo esto está orquestado con Docker Compose.

1. Abre un terminal en la raíz del proyecto.
2. Ejecuta el siguiente comando para construir las imágenes y levantar todos los contenedores en segundo plano:
   ```bash
   sudo docker compose up -d --build
   ```
3. Verifica que los 5 contenedores estén corriendo (`thothbot-rasa`, `thothbot-actions`, `thothbot-mariadb`, `thothbot-mongodb` y `thothbot-telegram`):
   ```bash
   sudo docker compose ps
   ```

*(Si es la primera vez que lo levantas, recuerda que el modelo de Rasa debe entrenarse dentro del contenedor usando `sudo docker compose exec rasa rasa train` y luego reiniciar el contenedor con `sudo docker compose restart rasa`)*.

---

## 3. Levantar ThothBot en Telegram

¡Buenas noticias! **Telegram ya está funcionando.**

En el archivo `docker-compose.yml` hemos incluido un contenedor especial llamado `telegram_proxy`. Este contenedor actúa como intermediario entre Telegram y Rasa usando una técnica llamada *polling* (lo que soluciona los problemas del canal nativo de Rasa 3.6.x).

### Pasos para usarlo:
1. Asegúrate de que el contenedor proxy está funcionando correctamente:
   ```bash
   sudo docker compose logs -f telegram_proxy
   ```
   Deberías ver un mensaje como: `Bot iniciado con polling...`
2. Abre Telegram (en tu móvil o versión de escritorio).
3. Busca tu bot por el nombre de usuario que registraste en BotFather.
4. Pulsa el botón **"Iniciar"** (o escribe `/start`).
5. El bot debería darte la bienvenida y mostrar los botones interactivos correctamente.

---

## 4. Levantar ThothBot en la Interfaz Web

La interfaz gráfica web es estática y consta de un archivo `index.html` ubicado en la carpeta `web_interface/`. Este archivo se conecta a Rasa a través de **WebSockets**.

### Paso 1: Configurar la IP/Dominio de conexión
Abre el archivo `web_interface/index.html` en un editor de texto y busca la siguiente línea en la parte inferior del código (dentro del `<script>` de `WebChat.default`):

```javascript
socketUrl: "https://thothbot.alcostepc.com", 
```

- **Si estás probando el bot en local (tu propio PC):** Cámbialo a `http://localhost:5005`.
- **Si el bot está en un VPS pero NO tiene dominio/HTTPS:** Cámbialo a `http://<IP_DE_TU_VPS>:5005`.
- **Si el bot está en producción con HTTPS (Nginx configurado):** Déjalo con el dominio de tu servidor (ej. `https://thothbot.alcostepc.com`).

### Paso 2: Ejecutar la interfaz web
Al ser un archivo HTML simple, no requiere un servidor complejo. Puedes usar cualquiera de estas opciones:

**Opción A: Abrir directamente (Local)**
Simplemente haz doble clic en el archivo `web_interface/index.html` y se abrirá en tu navegador predeterminado. El widget de chat aparecerá en la esquina inferior derecha.

**Opción B: Servidor Python ligero (Local / VPS)**
Si prefieres servirlo mediante HTTP (recomendado para evitar bloqueos CORS del navegador):
```bash
cd web_interface
python3 -m http.server 8000
```
Luego, entra en `http://localhost:8000` (o la IP de tu VPS por el puerto 8000) desde el navegador.

**Opción C: Live Server (Si usas VSCode)**
Haz clic derecho sobre el archivo `index.html` en Visual Studio Code y selecciona **"Open with Live Server"**.

**Opción D: Producción (VPS con Nginx)**
Si estás en el VPS, configura tu bloque de Nginx para que la raíz (`root`) apunte al directorio estático `web_interface`:
```nginx
server {
    listen 443 ssl;
    server_name thothbot.alcostepc.com;
    
    # Servir la interfaz gráfica HTML estática
    root /home/bernie/ThothBot/web_interface;
    index index.html;

    # Bloque de Proxy para Rasa WebSockets
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5005/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## Resumen de Funcionamiento

Con esto, la arquitectura queda de la siguiente forma:

- **Usuario en Telegram** ➔ Envía mensaje ➔ Llega a `telegram_proxy` (via polling) ➔ Reenvía mensaje internamente por la red de Docker a `rasa:5005/webhooks/rest/webhook`.
- **Usuario en Navegador** ➔ Abre el HTML ➔ El widget de chat conecta vía WebSockets directamente a `IP_Servidor:5005/socket.io/` ➔ Rasa procesa y responde.
- **Rasa** ➔ Llama internamente a `action_server:5055` para ejecutar las lógicas de Wikipedia, Ticketmaster o consultas en MariaDB/MongoDB.
