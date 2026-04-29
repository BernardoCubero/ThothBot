import requests

def buscar_en_wikipedia(monumento, idioma="es"):
    url = f"https://{idioma}.wikipedia.org/w/api.php"
    headers = {"User-Agent": "ThothBot/1.0 (proyecto TFG)"}
    params = {"action": "query", "list": "search", "srsearch": monumento, "format": "json", "srlimit": 1}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=4)
        data = response.json()
    except Exception as e:
        return None

    resultados = data.get("query", {}).get("search", [])
    if resultados:
        titulo = resultados[0]["title"]
        return titulo
    return None

print("EN:", buscar_en_wikipedia("castillo lizar", "en"))
print("ES:", buscar_en_wikipedia("castillo lizar", "es"))
