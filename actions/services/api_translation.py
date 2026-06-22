import requests

def traducir_es_en(texto):
    try:
        url = "https://api.mymemory.translated.net/get"
        params = {"q": texto, "langpair": "es|en"}
        r = requests.get(url, params=params, timeout=3)
        if r.status_code == 200:
            tr = r.json().get("responseData", {}).get("translatedText")
            if tr:
                return tr
    except:
        pass
    return texto
