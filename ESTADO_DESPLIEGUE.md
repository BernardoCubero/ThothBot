# Estado del Despliegue — ThothBot

> Última actualización: 2026-05-12 09:09h

---

## ✅ DESPLIEGUE COMPLETADO

- [x] Docker configurado correctamente en local
- [x] `docker-compose.yml` reescrito con 4 servicios (rasa, action_server, mariadb, mongodb)
- [x] `endpoints.yml` corregido (`http://action_server:5055/webhook`)
- [x] `.env` corregido (`MARIADB_HOST=db`)
- [x] `actions/actions.py` corregido (import `FollowupAction` desde `rasa_sdk.events`)
- [x] `requirements.txt` y `requirements-actions.txt` limpiados
- [x] `.dockerignore` actualizado (excluye `.rasa/`)
- [x] Imágenes construidas y subidas a Docker Hub:
  - `adsl7700/thothbot-rasa:latest`
  - `adsl7700/thothbot-actions:latest`
- [x] Archivos `docker-compose.yml` y `.env` copiados al VPS
- [x] Docker instalado en el VPS
- [x] `docker compose pull` ejecutado en el VPS
- [x] `docker compose up -d` ejecutado en el VPS (4 contenedores corriendo)
- [x] Modelo entrenado en el VPS (`rasa train` completado)
- [x] Carpeta `actions/` copiada al VPS (permisos corregidos con `chown`)
- [x] Tabla `usuarios` creada en MariaDB via SQLAlchemy (`Base.metadata.create_all`)
- [x] **Bot respondiendo correctamente en producción** ✅

---

## 🌐 Acceso al bot

```bash
# Health check
curl http://135.125.101.196:5005

# Enviar mensaje
curl -s -X POST http://135.125.101.196:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "usuario1", "message": "hola"}' | python3 -m json.tool
```

---

## 📋 Datos del servidor

| Campo    | Valor               |
|----------|---------------------|
| IP       | `135.125.101.196`   |
| Puerto   | `2224`              |
| Usuario  | `bernie`            |
| Ruta     | `~/ThothBot/`       |
| Rasa API | `:5005`             |
| Actions  | `:5055`             |
| MariaDB  | `:3307` (externo)   |
| MongoDB  | `:27018` (externo)  |

---

## 🔧 Comandos rápidos de referencia

```bash
# Conectarse al VPS
ssh -p 2224 bernie@135.125.101.196

# Ver logs en tiempo real
sudo docker compose logs -f rasa
sudo docker compose logs -f action_server

# Ver estado de contenedores
sudo docker compose ps

# Reiniciar un servicio
sudo docker compose restart rasa
sudo docker compose restart action_server

# Parar todo
sudo docker compose down

# Actualizar tras cambios (local → push → VPS)
# En local:
docker build -t adsl7700/thothbot-rasa:latest . && docker push adsl7700/thothbot-rasa:latest
docker build -t adsl7700/thothbot-actions:latest -f actions/Dockerfile . && docker push adsl7700/thothbot-actions:latest
# En el VPS:
sudo docker compose pull && sudo docker compose up -d

# Copiar actions actualizadas al VPS (si se modifican)
scp -P 2224 -r /home/bernie/proyectos/ThothBot/actions/ bernie@135.125.101.196:~/ThothBot/
# Y luego en el VPS:
sudo docker compose restart action_server

# Recrear tablas de MariaDB (si es necesario)
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

## ⚠️ Notas importantes

- La carpeta `actions/` en el VPS tiene un **volume mount** en docker-compose.yml. Si se actualizan las acciones en local, hay que copiarlas al VPS con `scp` y hacer `restart action_server`.
- El modelo Rasa se entrena **dentro del contenedor** y persiste mientras el contenedor no se elimine. Si se hace `docker compose down` (no solo `restart`), hay que reentrenar.
- Para que el modelo persista entre reinicios completos, añadir un volumen para `/app/models/` en el docker-compose.yml.
