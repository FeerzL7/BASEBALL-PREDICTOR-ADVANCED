import requests
from utils.constants import API_KEY, SPORT, REGION, MARKETS

def obtener_cuotas():
    url = f"https://api.the-odds-api.com/v4/sports/{SPORT}/odds"
    params = {
        "regions": REGION,
        "markets": MARKETS,
        "oddsFormat": "decimal",
        "apiKey": API_KEY
    }
    response = requests.get(url, params=params)

    try:
        data = response.json()
        if isinstance(data, dict) and data.get("message"):
            print("[ERROR] API Error:", data["message"])
            return []
        return data
    except ValueError:
        print("[ERROR] No se pudo decodificar el JSON de la API")
        return []
