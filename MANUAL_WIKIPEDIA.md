# Manual rapido: consultas a Wikipedia en ThothBot

Este manual explica como funciona la consulta a Wikipedia para informacion de monumentos y como diagnosticar fallos.

## Flujo actual

1. Se recibe el nombre del monumento desde la accion `action_info_monumento`.
2. Se normaliza texto (minusculas y sin tildes) en `ciudadNormalizada`.
3. Se busca un titulo en Wikipedia con `buscar_en_wikipedia(monumento)` usando la API de busqueda:
   - Endpoint: `https://es.wikipedia.org/w/api.php`
   - Parametros: `action=query`, `list=search`, `srsearch=<texto>`, `format=json`, `srlimit=1`
4. Con el titulo encontrado, se pide el resumen con `obtener_resumen_wikipedia(titulo)`:
   - Endpoint: `https://es.wikipedia.org/api/rest_v1/page/summary/<titulo>`
5. Se devuelve descripcion, extract corto y link.

## Punto critico obligatorio

Wikipedia puede responder `403` si no se envia cabecera `User-Agent`.

En este proyecto debe mantenerse esta cabecera en ambas funciones:
- `buscar_en_wikipedia`
- `obtener_resumen_wikipedia`

Valor usado:
- `ThothBot/1.0 (proyecto TFG)`

## Errores tipicos y causa

- `No encontre informacion fiable...`
  - La busqueda no devolvio titulo valido.
  - El resumen devolvio estado no 200 o cuerpo vacio.

- Respuesta `403` en busqueda
  - Falta `User-Agent`.

- Resultados malos o ambiguos
  - Nombre de monumento demasiado corto o generico.
  - Limpieza excesiva del texto (por ejemplo, quitar conectores utiles del nombre).

## Prueba rapida en terminal

Con el entorno del proyecto:

```bash
/home/bernie/proyectos/ThothBot/venv/bin/python -c "import sys; sys.path.append('/home/bernie/proyectos/ThothBot'); from actions.actions import buscar_en_wikipedia, obtener_resumen_wikipedia; q='templo de debod'; t=buscar_en_wikipedia(q); print('titulo=',t); r=obtener_resumen_wikipedia(t) if t else None; print('ok=', bool(r)); print((r or '')[:220])"
```

Salida esperada:
- `titulo=` con un titulo real de Wikipedia
- `ok= True`

## Checklist de diagnostico

1. Verificar que `buscar_en_wikipedia` usa `headers` con `User-Agent`.
2. Verificar que `requests.get` tiene `timeout`.
3. Confirmar `status_code == 200` antes de parsear JSON.
4. Confirmar que `query.search` tiene resultados.
5. Si no hay resultados, probar con texto de monumento mas especifico.

## Ubicacion del codigo

- `actions/actions.py`
  - `buscar_en_wikipedia`
  - `obtener_resumen_wikipedia`
  - `ActionInfoMonumento.run`
