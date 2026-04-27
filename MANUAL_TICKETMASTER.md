# Manual rápido: consultas a Ticketmaster en ThothBot

Este manual explica cómo funciona la consulta a la API Discovery de Ticketmaster para buscar eventos dinámicos y cómo diagnosticar posibles fallos.

## Flujo actual

1. Se recibe el nombre de la ciudad (desde un slot o extraído del propio texto) en la acción `action_buscar_eventos`.
2. Se analiza el texto del usuario para detectar palabras clave y asignar una clasificación al evento (por ejemplo: "concierto" -> `Music`, "teatro" -> `Arts & Theatre`, "partido" -> `Sports`).
3. Se realiza una petición HTTP `GET` a la API de Ticketmaster:
   - **Endpoint:** `https://app.ticketmaster.com/discovery/v2/events.json`
   - **Parámetros base:** `apikey=<TK_API_KEY>`, `countryCode=ES`, `city=<ciudad>`, `size=5`, `sort=date,asc`.
   - **Parámetros opcionales:** `classificationName=<clasificación>` (solo si el usuario especificó un tipo de evento).
4. Se procesa el JSON resultante. Ticketmaster anida los resultados, por lo que se extrae la lista de eventos desde `data.get("_embedded", {}).get("events", [])`.
5. Se formatea la respuesta en Markdown mostrando el nombre de los primeros 5 eventos próximos y, si está disponible, se añade un enlace (`url`) directo para ver detalles o comprar entradas.

## Punto crítico obligatorio

Ticketmaster utiliza un formato de respuesta JSON tipo **HAL (Hypertext Application Language)**. 
- Si hay resultados, la lista de eventos se aloja dentro del nodo raíz llamado `_embedded`.
- **¡Importante!** Si una búsqueda no encuentra ningún evento, la API devuelve un código de éxito `200 OK`, pero **el nodo `_embedded` desaparece completamente** del JSON. Intentar acceder usando `data["_embedded"]["events"]` provocaría un error fatal en el bot (`KeyError`). Por ello, siempre es obligatorio navegar de forma segura por el JSON usando diccionarios `.get(clave, valor_por_defecto)`.

## Errores típicos y causa

- **`No tengo eventos próximos para <ciudad> en este momento.`**
  - La petición se completó bien, pero la ciudad no tiene eventos en el catálogo de Ticketmaster (el JSON no tiene `_embedded`). Es normal en pueblos o ciudades pequeñas.
- **`Hubo un problema al consultar los eventos en Ticketmaster.`**
  - La API devolvió un código HTTP de error (ej. 401, 403).
  - *Causa principal:* La variable de entorno `TKMASTER` del archivo `.env` no se ha cargado correctamente, la clave no es válida, o se ha sobrepasado el límite de uso diario para cuentas gratuitas de desarrollador.
- **`Hubo un problema de conexión al buscar los eventos.`**
  - Ha saltado una excepción de red o el tiempo de espera configurado (`timeout=10`) se ha agotado. 

## Prueba rápida en terminal

Para verificar si la API Key está activa y devuelve datos correctamente desde el entorno del proyecto, puedes pegar el siguiente comando en consola:

```bash
/home/bernie/proyectos/ThothBot/venv/bin/python -c "import os, requests; from dotenv import load_dotenv; load_dotenv('/home/bernie/proyectos/ThothBot/.env'); key=os.getenv('TKMASTER'); r=requests.get('https://app.ticketmaster.com/discovery/v2/events.json', params={'apikey':key, 'countryCode':'ES', 'city':'madrid', 'size':1}); print('HTTP', r.status_code); ev=r.json().get('_embedded', {}).get('events', []) if r.status_code==200 else []; print('OK' if ev else 'No eventos', '-', ev[0]['name'] if ev else '')"
```

**Salida esperada:**
- `HTTP 200`
- `OK - <Nombre de un evento real en Madrid>`

## Checklist de diagnóstico

1. Revisar que el archivo `.env` existe en la raíz del proyecto y contiene la línea `TKMASTER=tu_api_key`.
2. Verificar que al arrancar el servidor `rasa run actions`, la librería `python-dotenv` carga correctamente las variables de entorno (ningún aviso de variables no encontradas).
3. Inspeccionar los logs en la terminal donde corre el Actions Server, ya que hemos dejado programados varios `print()` que mostrarán el código HTTP y el mensaje de error original de Ticketmaster en caso de fallo.
