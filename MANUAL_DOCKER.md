# Manual de Despliegue con Docker — ThothBot

Este documento describe cómo levantar el entorno completo de ThothBot usando Docker Compose. El entorno incluye 4 contenedores: el motor de Rasa, el servidor de acciones, MariaDB y MongoDB.

---

## Requisitos previos

- Sistema operativo Linux (probado en Ubuntu 24.04)
- Docker Engine instalado (versión 20.10 o superior)
- Docker Compose Plugin (integrado en Docker v2, **no** el antiguo `docker-compose`)

> **Nota:** En versiones modernas de Docker, el comando es `docker compose` (sin guion).  
> Si usas el antiguo `docker-compose` y recibes `orden no encontrada`, instala Docker Engine actualizado.

### Verificar la instalación de Docker

```bash
docker --version
docker compose version
```

---

## Arquitectura del entorno

```
┌─────────────────────────────────────────────┐
│              Red: thothbot-net              │
│                                             │
│  ┌──────────────┐    ┌───────────────────┐  │
│  │  thothbot-   │───▶│  thothbot-actions │  │
│  │    rasa      │    │  (rasa-sdk:3.6.2) │  │
│  │ :5005        │    │  :5055            │  │
│  └──────────────┘    └───────────────────┘  │
│         │                     │             │
│  ┌──────▼──────┐    ┌─────────▼─────────┐  │
│  │  thothbot-  │    │  thothbot-mongodb  │  │
│  │   mariadb   │    │  (mongo:latest)    │  │
│  │  :3307      │    │  :27018            │  │
│  └─────────────┘    └────────────────────┘  │
└─────────────────────────────────────────────┘
```

| Contenedor          | Imagen base             | Puerto externo |
|---------------------|-------------------------|----------------|
| `thothbot-rasa`     | `rasa/rasa:3.6.20-full` | `5005`         |
| `thothbot-actions`  | `rasa/rasa-sdk:3.6.2`   | `5055`         |
| `thothbot-mariadb`  | `mariadb:10.6`          | `3307`         |
| `thothbot-mongodb`  | `mongo:latest`          | `27018`        |

---

## Configuración previa

### 1. Archivo `.env`

El archivo `.env` en la raíz del proyecto contiene las variables de entorno necesarias. Dentro de Docker, los hosts de las bases de datos **deben apuntar al nombre del servicio**, no a `localhost`.

```env
GEOAPIFY_API_KEY=tu_clave_aqui
TKMASTER=tu_clave_aqui

# Base de datos MariaDB
MARIADB_USER=root
MARIADB_PASSWORD=1234
MARIADB_HOST=db          # ← nombre del servicio en Docker, NO localhost
MARIADB_PORT=3306
MARIADB_DB=thothbot_db
```

### 2. Archivos ignorados en la build

El archivo `.dockerignore` excluye los siguientes directorios para evitar conflictos de permisos y reducir el tamaño de la imagen:

```
venv/
.rasa/       ← Caché de entrenamiento local (permisos de root incompatibles)
.git/
__pycache__/
```

> **Importante:** `.rasa/` debe estar excluida porque la caché local de entrenamiento  
> es generada por `root` en local y el contenedor corre como usuario `1001`,  
> lo que causaría el error `attempt to write a readonly database`.

---

## Primera puesta en marcha

### Paso 1: Construir y levantar todos los contenedores

```bash
sudo docker compose up --build
```

Esto descargará las imágenes base (si no existen), construirá las imágenes personalizadas de Rasa y el servidor de acciones, e iniciará los 4 contenedores.

### Paso 2: Entrenar el modelo de Rasa

El modelo debe entrenarse **dentro del contenedor** para garantizar la compatibilidad. Abre una segunda terminal y ejecuta:

```bash
sudo docker compose exec rasa rasa train
```

El entrenamiento puede tardar varios minutos. Cuando finalice, verás:

```
Your Rasa model is trained and saved at models/XXXXXXXX-modelo.tar.gz
```

### Paso 3: Reiniciar Rasa para cargar el nuevo modelo

```bash
sudo docker compose restart rasa
```

El bot ya está completamente operativo.

---

## Uso diario

### Levantar el entorno (sin reconstruir)

```bash
sudo docker compose up -d
```

### Parar el entorno

```bash
sudo docker compose down
```

### Ver logs en tiempo real

```bash
# Todos los contenedores
sudo docker compose logs -f

# Solo uno
sudo docker compose logs -f rasa
sudo docker compose logs -f action_server
```

---

## Flujo de trabajo durante el desarrollo

| Cambio realizado | Acción necesaria |
|---|---|
| Modificar `actions/actions.py` | `sudo docker compose restart action_server` |
| Modificar intents, stories, domain | `sudo docker compose exec rasa rasa train` → `sudo docker compose restart rasa` |
| Modificar `requirements-actions.txt` | `sudo docker compose up --build action_server` |
| Modificar `Dockerfile` o `docker-compose.yml` | `sudo docker compose up --build` |

> **Ventaja del volumen selectivo:** La carpeta `actions/` está montada como volumen  
> en el contenedor `action_server`. Esto permite que los cambios en `actions.py`  
> se reflejen sin necesidad de reconstruir la imagen, solo reiniciando el servicio.

---

## Resolución de problemas comunes

### `order not found: docker-compose`
Usa la sintaxis nueva: `docker compose` (sin guion).

### `./entrypoint.sh: no such file or directory`
Causado por montar un volumen sobre `/app` en el contenedor de Rasa, lo que sobreescribe el `entrypoint.sh` de la imagen base. **No montar volúmenes sobre `/app` en el servicio `rasa`.**

### `attempt to write a readonly database`
La carpeta `.rasa/` fue copiada dentro de la imagen con permisos incorrectos. Asegúrate de que `.rasa/` está en el `.dockerignore` y reconstruye la imagen.

### `ModuleNotFoundError: No module named 'rasa'`
El servidor de acciones usa `rasa-sdk`, que **no incluye** el paquete completo `rasa`.  
Los imports en `actions.py` deben ser de `rasa_sdk`, por ejemplo:
```python
# ❌ Incorrecto
from rasa.shared.core.events import FollowupAction

# ✅ Correcto
from rasa_sdk.events import FollowupAction
```

### `bcc==0.29.1` no encontrado al instalar dependencias
Los archivos `requirements.txt` no deben contener paquetes del sistema operativo (generados con `pip freeze` global). Solo deben incluir las dependencias reales del proyecto:
```
requests
python-dotenv
pymongo
SQLAlchemy
PyMySQL
cryptography
```

---

## Persistencia de datos

Los datos de las bases de datos se almacenan en **volúmenes nombrados de Docker**, por lo que sobreviven a reinicios y reconstrucciones de contenedores:

| Volumen               | Datos almacenados              |
|-----------------------|-------------------------------|
| `thothbot_mariadb_data` | Usuarios registrados (MariaDB) |
| `thothbot_mongodb_data` | Logs de conversaciones (MongoDB) |

Para eliminar los datos y empezar desde cero:

```bash
sudo docker compose down -v
```

> ⚠️ El flag `-v` elimina los volúmenes. Úsalo solo si quieres borrar todos los datos.
