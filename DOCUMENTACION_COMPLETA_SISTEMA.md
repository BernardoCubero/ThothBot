# Documentación Técnica Completa: Arquitectura e Implementación de ThothBot

## ¿Qué es ThothBot y para qué sirve?

**ThothBot** es un asistente virtual conversacional especializado en ofrecer **información turística** en tiempo real. Su objetivo principal es ayudar a los viajeros y usuarios a descubrir ciudades interactuando en lenguaje natural. El bot funciona como un guía turístico inteligente capaz de recomendar monumentos, proporcionar resúmenes históricos e información detallada sobre puntos de interés, así como buscar eventos culturales, musicales o deportivos en la ciudad elegida.

Diseñado para ser altamente accesible, ThothBot puede utilizarse tanto a través de una interfaz web propia como desde la aplicación de mensajería Telegram, facilitando la planificación de viajes o la búsqueda de planes sobre la marcha.

Este documento detalla exhaustivamente el diseño, la arquitectura de microservicios, los retos técnicos resueltos y las decisiones de implementación tomadas durante el desarrollo y estabilización de este sistema basado en el framework Rasa.

---

## 1. Arquitectura General del Sistema

ThothBot se implementa bajo una arquitectura de microservicios contenerizada mediante **Docker Compose**. Esto permite desacoplar las responsabilidades y escalar cada componente de forma independiente.

```
[Interfaz Web Browser]               [Telegram App]
         │ (Socket.io / HTTPS)              │ (Polling)
         ▼                                  ▼
[Proxy Reverso Nginx VPS]            [Telegram Proxy (Contenedor)]
         │ (Proxy a /socket.io)             │ (REST API a /webhooks/rest)
         ▼                                  ▼
   [Rasa Core & NLU (Contenedor thothbot-rasa:5005)]
         │
         │ (HTTP POST /webhook)
         ▼
   [Servidor de Acciones SDK (Contenedor thothbot-actions:5055)]
         │
         ├─► [MariaDB (thothbot-mariadb:3306)] ──► Almacena perfiles de usuarios registrados
         └─► [MongoDB (thothbot-mongodb:27017)] ──► Guarda logs de telemetría conversacional
```

### Componentes y Roles

1. **Rasa (`thothbot-rasa`)**:
   * **Rol**: Motor central de procesamiento de lenguaje natural (NLU) y gestión de diálogos (Core).
   * **Función**: Clasifica intenciones (`intents`), extrae entidades (`ciudad`, `monumento`, etc.) y decide la siguiente acción a ejecutar basándose en reglas (`rules.yml`) e historias (`stories.yml`).
2. **Telegram Proxy (`thothbot-telegram`)**:
   * **Rol**: Adaptador intermedio de mensajería.
   * **Función**: Elimina los problemas de estabilidad de la conexión nativa de Rasa con Telegram y maneja el formato de los mensajes (botones en línea y conversión de Markdown).
3. **Servidor de Acciones (`thothbot-actions`)**:
   * **Rol**: Backend de ejecución lógica.
   * **Función**: Servidor SDK de Rasa que ejecuta código personalizado en Python. Es el encargado de consultar APIs externas (Wikipedia, Ticketmaster), conectarse a las bases de datos y resolver la lógica de desambiguación.
4. **MariaDB (`thothbot-mariadb`)**:
   * **Rol**: Base de datos relacional.
   * **Función**: Almacena de forma persistente los perfiles de usuario registrados a través de la conversación (nombre, ciudad de origen, país).
5. **MongoDB (`thothbot-mongodb`)**:
   * **Rol**: Base de datos NoSQL documental.
   * **Función**: Guarda logs detallados de cada interacción (intención detectada, mensaje original, contexto geográfico) para fines de auditoría y análisis de datos.

---

## 2. El Proxy de Telegram

### El Problema Técnico de Origen
Rasa provee un canal nativo para Telegram. Sin embargo, en entornos de producción con Rasa 3.6.x ejecutándose bajo Python 3.10+, la librería interna `pyTelegramBotAPI` sufre de bloqueos intermitentes debido a conflictos en el bucle de eventos asíncronos de Python (`RuntimeError: Event loop is closed`). Esto provocaba que el bot de Telegram dejara de responder sin lanzar fallos críticos aparentes en el contenedor.

### La Solución: Telegram Proxy Ligero
Para resolver esto, diseñamos un servicio intermedio escrito en Python (`telegram_proxy/bot.py`) utilizando la librería moderna `python-telegram-bot` (v20+). 

```
[Usuario Telegram] 
       │ (Mensaje de Texto)
       ▼
[Telegram Proxy (Polling)] ──(HTTP POST REST)──> [Rasa REST Endpoint (/webhooks/rest)]
       │                                                       │
[Usuario Telegram] <──(Envío con Formateo)── [Respuesta JSON] ◄─┘
```

#### Características del Proxy:
1. **Consumo vía REST**: El proxy recibe los mensajes de Telegram mediante *polling* seguro, los reenvía al endpoint REST de Rasa (`http://rasa:5005/webhooks/rest/webhook`) usando el `user_id` de Telegram como el identificador de conversación (`sender`).
2. **Tratamiento del Formato**:
   * **Markdown**: Convierte la sintaxis estándar de Markdown de GitHub (usada por las APIs de Rasa/Wikipedia) a la sintaxis compatible con Telegram MarkdownV1/V2 (evitando que el bot falle por caracteres no escapados).
   * **Enlaces a Botones**: Para mejorar la experiencia de usuario, parsea expresiones tipo `[Texto](URL)` y las extrae dinámicamente convirtiéndolas en botones interactivos en línea (`InlineKeyboardMarkup`), dejando el texto del chat limpio y legible.

---

## 3. Extracción de Entidades y Lógica de Desambiguación (Wikipedia)

Uno de los mayores desafíos en asistentes virtuales turísticos es la **precisión en la resolución de nombres geográficos**. Consultas como *"información de Córdoba"* tendían a devolver resultados erróneos de municipios homónimos más pequeños (ej. *"Villaviciosa de Córdoba"*) o a colapsar al toparse con páginas de desambiguación en Wikipedia.

### Algoritmo de Resolución Geográfica Implementado

Para solucionar esto, robustecimos el flujo dentro del método `ActionInfoMonumento` en `actions/actions.py`:

```
[Consulta del Usuario] 
       │
       ▼
[Filtro Stopwords Ampliado] ──> (Elimina "de", "el", "hablame sobre", etc.)
       │
       ▼
[Verificación de Duplicación] ──> (Evita queries redundantes como "Córdoba Córdoba")
       │
       ▼
[Búsqueda Opensearch Wikipedia] ──> ¿Hay Título?
       │                                 │ (No)
       │ (Sí)                            ▼
       │                          [Fallback Directo REST]
       ▼
[Validación de Similitud (es_match_valido)]
       │
       ├─► Coincidencia Exacta? ──► SÍ (Aceptar)
       ├─► .startswith()? ────────► SÍ (Aceptar)
       └─► Ratio difflib >= 0.65? ──► SÍ (Aceptar)
               │ (No)
               ▼
   [Rechazar / Fallback España Ciudad]
```

#### 1. Filtro Stopwords y Limpieza Conversacional (`stopwords_extra`)
Las frases conversacionales introducen ruido que confunde a los buscadores indexados. Añadimos un conjunto extendido de *stopwords* en caliente dentro de la lógica del servidor de acciones para limpiar la consulta del usuario:
```python
stopwords_extra = {
    "de", "del", "en", "a", "al", "los", "las", "le", "la", "el",
    "hablame", "cuentame", "buscame", "enseñame", "muestrame", "dame",
    "sobre", "acerca", "respecto"
}
```
Esto asegura que la frase *"háblame sobre la Mezquita"* limpie todo el preámbulo y busque únicamente `"mezquita"`.

#### 2. Prevención de Duplicación de Contexto
Anteriormente, si el slot de la `ciudad` estaba configurado en `"Cordoba"`, al buscar un monumento genérico la query resultaba en `"de cordoba Cordoba"`. Implementamos un control de subcadenas que impide concatenar el contexto geográfico si el término de búsqueda ya contiene la ciudad:
```python
ciudad_ctx_norm = ciudadNormalizada(ciudad_ctx) if ciudad_ctx else ""
monumento_norm = ciudadNormalizada(monumento)
if ciudad_ctx and ciudad_ctx_norm not in monumento_norm:
    query_wiki = f"{monumento} {ciudad_ctx}"
else:
    query_wiki = monumento
```

#### 3. Validación Estricta de Coincidencias (`es_match_valido`)
Para evitar desvíos geográficos (ej. buscar *"Córdoba"* y que devuelva *"Villaviciosa de Córdoba"* porque contiene la palabra), implementamos controles geométricos de texto:
* **Coincidencia Exacta** tras normalizar caracteres y acentos.
* **Coincidencia por Inicio**: El título de Wikipedia debe empezar por la búsqueda, o viceversa (`t_n.startswith(m_n)`). Esto permite buscar `"mezquita"` y validar `"Mezquita-Catedral de Córdoba"`.
* **Filtro de Similitud Adaptativo**: Evaluamos el ratio de `SequenceMatcher` ajustado a un umbral óptimo de `0.65`. Suficientemente tolerante para emparejar términos complejos, pero lo bastante estricto para bloquear falsos positivos regionales (cuyo ratio ronda el `0.60` o menos).

#### 4. Mecanismo de Fallback para Desambiguaciones (El caso "Córdoba")
Cuando un usuario consulta por una gran capital (como "Córdoba"), Wikipedia por defecto devuelve una **Página de Desambiguación** (tipo `disambiguation` que lista Córdoba España, Córdoba Argentina, etc.). Nuestro motor la descarta al no contener información útil. 

Para resolver este bloqueo, implementamos un *fallback geográfico inteligente*: si el resultado es descartado por ser de desambiguación, el bot realiza una segunda búsqueda añadiendo la palabra clave de geolocalización e intención:
`f"{titulo} España ciudad"` (ej. `"Córdoba España ciudad"`). 
Esto fuerza a la API a devolver el artículo exacto de **Córdoba (España)** de forma totalmente transparente para el usuario.

---

## 4. Persistencia de Datos Dual

Diseñamos e implementamos un sistema híbrido de persistencia para satisfacer dos necesidades operativas distintas: estructuración de datos de usuario e histórico de telemetría conversacional.

### MariaDB y SQLAlchemy (Datos Relacionales)
Se utiliza para almacenar datos estructurados y persistentes de los usuarios. 

* **ORM**: SQLAlchemy.
* **Modelo**:
```python
class Usuario(Base):
    __tablename__ = 'usuarios'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(255), unique=True, nullable=False)
    nombre = Column(String(100), nullable=True)
    ciudad_origen = Column(String(100), nullable=True)
    pais = Column(String(100), nullable=True)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
```
* **Dinámica**: Cuando el usuario interactúa, Rasa comprueba si el `conversation_id` existe en MariaDB. Si es un usuario registrado, lo saluda de forma personalizada utilizando su nombre y procedencia. Si no, arranca un formulario conversacional (`usuario_form`) para registrarlo. 
* **Inicialización Robusta**: Implementamos la creación de tablas en caliente al iniciar el contenedor (`Base.metadata.create_all(engine)`), lo que evita caídas del backend si la base de datos se despliega limpia.

### MongoDB (Histórico Documental)
Cada vez que el bot clasifica una intención de búsqueda, el servidor de acciones invoca un logger asíncrono para documentar la interacción en MongoDB.

* **Estructura Documental**:
```json
{
  "_id": ObjectId("..."),
  "timestamp": "2026-05-19T21:18:15.123Z",
  "intent": "info_monumento",
  "ciudad": "cordoba",
  "mensaje": "informacion sobre la mezquita"
}
```
Esto permite realizar análisis futuros de Big Data sobre qué monumentos despiertan mayor interés turístico y qué ciudades son las más consultadas.

---

## 5. Interfaz Web e Integración con socket.io

La interfaz de usuario del navegador (`web_interface/index.html`) es una interfaz moderna, minimalista y responsiva diseñada con CSS puro (variables CSS, flexbox, efectos blur y animaciones dinámicas de fondo).

### El Canal Webchat (Socket.io)
Para habilitar el chat interactivo en tiempo real en la web, configuramos el canal **Socket.io** en Rasa:
1. **Configuración en `credentials.yml`**: Habilitamos el socket con persistencia de sesión:
```yaml
socketio:
  user_message_evt: user_uttered
  bot_message_evt: bot_uttered
  session_persistence: true
```
2. **Proxy Nginx en el VPS**: Para que la web (servida bajo HTTPS) pueda comunicarse de forma segura con el contenedor Rasa (HTTP) sin violar las políticas de contenido mixto del navegador, configuramos una redirección de WebSockets en el archivo `/etc/nginx/sites-enabled/thothbot`:
```nginx
location /socket.io/ {
    proxy_pass http://127.0.0.1:5005/socket.io;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_cache_bypass $http_upgrade;
}
```
Esto permite encapsular todo el tráfico del bot bajo el mismo certificado SSL del dominio `thothbot.alcostepc.com`.

---

## 6. Sistema de Seguridad y Mantenimiento (Backups)

Para mitigar riesgos y prevenir pérdidas de datos operacionales, creamos un set de scripts de automatización de copias de seguridad en la ruta `scripts/`.

### 1. `scripts/backup.sh` (Copia de Seguridad)
Este script realiza las siguientes acciones de forma automática y secuencial:
1. Extrae las credenciales del archivo `.env` del VPS.
2. Ejecuta un `mysqldump` en caliente dentro del contenedor MariaDB y redirige el flujo de datos para guardar el archivo `.sql` en local.
3. Descarga mediante SCP los archivos de configuración críticos del VPS (`credentials.yml` y `.env`).
4. Empaqueta y comprime en formato `.tar.gz` todo el código fuente del proyecto, modelos entrenados de Rasa y recursos estáticos.
5. Sincroniza mediante `rsync` cualquier cambio del código local al servidor VPS para asegurar que producción está al día.

### 2. `scripts/restore.sh` (Restauración del Sistema)
En caso de un fallo catastrófico (como el borrado accidental de volúmenes o corrupción de configuraciones), este script reconstruye el entorno productivo a partir de un directorio de backup:
1. Re-inyecta el volcado SQL directamente en el contenedor MariaDB.
2. Restaura los archivos `credentials.yml` y `.env` originales.
3. Reinicia los servicios de Rasa y el Action Server en el VPS para aplicar los cambios de inmediato.

---

## Conclusión

**ThothBot** ha pasado de ser un bot conversacional con dependencias inestables a consolidarse como una **aplicación empresarial robusta, desacoplada y tolerante a fallos**. La combinación de un proxy externo de mensajería, lógica adaptativa para desambiguar consultas lingüísticas, persistencia híbrida estructurada/documental y automatización de respaldos garantiza que el sistema esté preparado para una defensa académica impecable y un uso real estable en producción.
