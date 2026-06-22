def extraer_ciudad_del_mensaje(tracker):
    # Prioriza entidad ciudad del ultimo mensaje para permitir cambiar de ciudad.
    entities = tracker.latest_message.get("entities") or []
    for entidad in entities:
        if entidad.get("entity") == "ciudad" and entidad.get("value"):
            val = entidad.get("value")
            if val and not val.strip().startswith("/"):
                return val

    # Si el intent es solo ciudad, usar el texto completo como nuevo valor.
    intent = (tracker.latest_message.get("intent") or {}).get("name")
    texto = (tracker.latest_message.get("text") or "").strip()
    if intent == "consultar_ciudad" and texto and not texto.startswith("/"):
        return texto

    return None
