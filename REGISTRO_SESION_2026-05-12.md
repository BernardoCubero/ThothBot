# Registro de Sesión — Despliegue y Activación Telegram
**Fecha:** 2026-05-12  
**Duración:** ~08:50h – 10:00h  
**Objetivo:** Verificar despliegue Docker en VPS y activar integración con Telegram

---

## ✅ Resumen de estado al inicio

El stack Docker estaba corriendo en el VPS (`135.125.101.196`) con 4 contenedores activos, y el entrenamiento de Rasa había terminado durante la noche.

---

## 🐛 Problemas encontrados y soluciones aplicadas

---

### Problema 1 — `curl` al bot devolvía "Connection reset by peer"

**Síntoma:**
```
curl: (56) Recv failure: Connection reset by peer
```

**Causa:** Rasa aún estaba cargando el modelo TED/DIET al hacer el curl. No era un error real, sino que el servidor no había terminado de inicializarse.

**Solución:** Esperar ~2 minutos a que terminase la carga del modelo. El `curl -v` posterior mostró `Hello from Rasa: 3.6.20`.

---

### Problema 2 — Action server sin acciones registradas

**Síntoma:**
```
ERROR rasa_sdk.endpoint - No registered action found for name 'action_buscar_monumentos'
```

**Causa:** El `docker-compose.yml` monta `./actions:/app/actions` como volumen, pero en el VPS la carpeta `actions/` no existía (solo se habían copiado `docker-compose.yml` y `.env`). El volumen vacío sobreescribía las acciones de la imagen.

**Solución:**
```bash
# Arreglar permisos (la carpeta la había creado Docker con sudo)
sudo chown -R bernie:bernie ~/ThothBot/actions/

# Copiar desde local
scp -P 2224 -r /home/bernie/proyectos/ThothBot/actions/ bernie@135.125.101.196:~/ThothBot/

# Reiniciar el action server
sudo docker compose restart action_server
```

---

### Problema 3 — Tabla `usuarios` no existía en MariaDB

**Síntoma:**
```
sqlalchemy.exc.ProgrammingError: (1146, "Table 'thothbot_db.usuarios' doesn't exist")
```

**Causa:** La base de datos MariaDB arrancó vacía. SQLAlchemy no crea las tablas automáticamente al iniciar; hay que llamar a `Base.metadata.create_all()` explícitamente.

**Solución:** Ejecutar la creación de tablas dentro del contenedor `action_server`:
```bash
sudo docker compose exec action_server python3 -c "
import os, sys; sys.path.insert(0, '/app')
from models.usuario import Base
from sqlalchemy import create_engine
url = f'mysql+pymysql://{os.environ[\"MARIADB_USER\"]}:{os.environ[\"MARIADB_PASSWORD\"]}@{os.environ[\"MARIADB_HOST\"]}/{os.environ[\"MARIADB_DB\"]}'
Base.metadata.create_all(create_engine(url))
print('Tablas creadas.')
"
```

---

### Problema 4 — Modelo Rasa no persistía entre reinicios

**Síntoma:** Al hacer `docker compose down` + `up`, el modelo entrenado desaparecía porque se guardaba dentro del contenedor (no persistido en el host).

**Causa:** Faltaba un volumen para `/app/models/` en el servicio `rasa`.

**Solución:** Añadir volumen en `docker-compose.yml`:
```yaml
rasa:
  volumes:
    - ./models:/app/models
```

**Nota adicional:** Al montar el volumen, el directorio del host necesita permisos del usuario `1001` (usuario interno del contenedor Rasa):
```bash
sudo chown -R 1001:1001 ~/ThothBot/models/
```

---

### Problema 5 — nginx sirviendo página por defecto en lugar de Rasa

**Síntoma:** `curl https://thothbot.alcostepc.com` devolvía la página "Welcome to nginx!" en vez de `Hello from Rasa`.

**Causa:** El sitio `default` de nginx estaba activo y tenía prioridad sobre el sitio `thothbot`, además de generar un warning de `conflicting server name`.

**Solución:**
```bash
# Desactivar el sitio default
sudo rm /etc/nginx/sites-enabled/default

# Reescribir el config del sitio con el bloque HTTPS correcto
sudo tee /etc/nginx/sites-available/thothbot > /dev/null <<'EOF'
server {
    listen 80;
    server_name thothbot.alcostepc.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name thothbot.alcostepc.com;
    ssl_certificate /etc/letsencrypt/live/thothbot.alcostepc.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/thothbot.alcostepc.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://localhost:5005;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo nginx -t && sudo systemctl reload nginx
```

---

### Problema 6 — `credentials.yml` con claves sueltas a nivel raíz

**Síntoma:**
```
RasaException: Failed to find input channel class for 'access_token'. Unknown input channel.
```

**Causa:** En el `credentials.yml` había un bloque antiguo de Telegram **sin indentar** bajo ningún canal (a nivel raíz del YAML):
```yaml
# ← estas líneas estaban sueltas, no bajo ningún canal
access_token: "${TELEGRAM_KEY}"
verify: "thothbot_tfg_bot"
webhook_url: "https://<your domain>/webhooks/telegram"
```
Rasa interpretaba `access_token` como nombre de canal, no como propiedad.

**Solución:** Eliminar esas líneas sueltas del `credentials.yml`.

---

### Problema 7 — Rasa no expande variables de entorno en `credentials.yml`

**Síntoma:**
```
aiogram.utils.exceptions.ValidationError: Token is invalid!
```

**Causa:** Rasa 3.6.x **no expande** variables de entorno con la sintaxis `${VAR}` en `credentials.yml`. La cadena literal `${TOKEN_TELEGRAM}` era pasada a aiogram como token, que la rechazaba por inválida.

**Solución:** Poner el token directamente en el archivo:
```yaml
telegram:
  access_token: "token_telegram
  verify: "thothbot_verify"
  webhook_url: "https://thothbot.alcostepc.com/webhooks/telegram/webhook"
```

---

### Problema 8 — Bug `RuntimeError: Event loop is closed` en canal Telegram nativo de Rasa

**Síntoma:**
```
RuntimeError: Event loop is closed
  File "rasa/core/channels/telegram.py", line 223, in message
    credentials = await out_channel.get_me()
```

**Causa:** Bug conocido en Rasa 3.6.x con aiogram. La sesión `aiohttp.ClientSession` se crea durante el arranque en un event loop y se intenta usar en otro (el de Sanic), que ya está cerrado. El método `get_me()` se llama en cada mensaje recibido.

**Solución:** Crear un servicio proxy independiente (`telegram_proxy`) usando `python-telegram-bot` v20 con **polling** (sin webhook), que reenvía mensajes a la API REST de Rasa:

```
Telegram ──polling──► telegram_proxy (python-telegram-bot)
                              │
                              ▼ HTTP POST
                       Rasa REST API :5005
```

Archivos creados:
- `telegram_proxy/bot.py` — script del proxy
- `telegram_proxy/Dockerfile` — imagen Python 3.10-slim
- `telegram_proxy/requirements-proxy.txt` — `python-telegram-bot==20.7`, `requests`

Añadido al `docker-compose.yml` como nuevo servicio `telegram_proxy`.

---

### Problema 9 — `docker compose build` fallaba por `build:` en servicios con imagen pre-construida

**Síntoma:**
```
target rasa: failed to solve: failed to read dockerfile: open Dockerfile: no such file or directory
```

**Causa:** Los servicios `rasa` y `action_server` tenían tanto `image:` como `build:` en el `docker-compose.yml`. En el VPS no existe el `Dockerfile` local, por lo que `--build` fallaba.

**Solución:** Eliminar los bloques `build:` de los servicios que usan imagen de Docker Hub. Solo `telegram_proxy` necesita `build:` (se construye localmente en el VPS).

---

## 📦 Archivos modificados en esta sesión

| Archivo | Cambio |
|---------|--------|
| `docker-compose.yml` | Añadido volumen `models/`, volumen `credentials.yml`, servicio `telegram_proxy`, eliminados bloques `build:` innecesarios |
| `credentials.yml` | Añadida sección `telegram:` con token real, eliminadas claves sueltas |
| `.env` | Añadida variable `TOKEN_TELEGRAM` |
| `telegram_proxy/bot.py` | **NUEVO** — Proxy Telegram → Rasa |
| `telegram_proxy/Dockerfile` | **NUEVO** |
| `telegram_proxy/requirements-proxy.txt` | **NUEVO** |

---

## 🎯 Estado al final de la sesión

| Servicio | Estado |
|----------|--------|
| Rasa 3.6.20 | ✅ Corriendo, modelo cargado |
| Action Server | ✅ 9 acciones registradas |
| MariaDB | ✅ Tabla `usuarios` creada |
| MongoDB | ✅ Corriendo |
| nginx + SSL | ✅ `https://thothbot.alcostepc.com` activo |
| Telegram Bot | ✅ **Funcionando via proxy polling** |

**El bot responde correctamente en Telegram** — intents reconocidos, monumentos, eventos y registro de usuarios operativos.

---

## ⚠️ Pendiente / Mejoras futuras

- [ ] Mejorar calidad de resultados de monumentos (Geoapify devuelve POIs poco relevantes)
- [ ] Implementar interfaz gráfica web en `https://thothbot.alcostepc.com`
- [ ] Añadir creación automática de tablas al arrancar (en lugar de hacerlo manualmente)
