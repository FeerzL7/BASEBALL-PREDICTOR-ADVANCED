# context.py
import requests
from datetime import datetime
import pytz

# Coordenadas geográficas de estadios conocidos
COORDENADAS_ESTADIOS = {
    'Coors Field': (39.7559, -104.9942),
    'Fenway Park': (42.3467, -71.0972),
    'Dodger Stadium': (34.0739, -118.2390),
    'Petco Park': (32.7076, -117.1570),
    'Yankee Stadium': (40.8296, -73.9262),
    'Globe Life Field': (32.7473, -97.0847),
    'Oakland Coliseum': (37.7516, -122.2005),
    'default': (40.0, -100.0)  # fallback para estadios no definidos
}

# Traducción de códigos de clima (opcional)
CLIMA_CODES = {
    0: 'Despejado',
    1: 'Principalmente despejado',
    2: 'Parcialmente nublado',
    3: 'Nublado',
    45: 'Niebla',
    51: 'Llovizna ligera',
    61: 'Lluvia moderada',
    71: 'Nieve ligera',
    95: 'Tormenta',
}


def obtener_clima(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true"
        }
        response = requests.get(url, params=params, timeout=10)
        clima = response.json().get('current_weather', {})
        return {
            'temperatura': clima.get('temperature', 22),
            'viento_kph': clima.get('windspeed', 10),
            'condiciones': CLIMA_CODES.get(clima.get('weathercode'), 'desconocido')
        }
    except Exception as e:
        print(f"[ERROR] Al obtener clima: {e}")
        return {'temperatura': 22, 'viento_kph': 10, 'condiciones': 'desconocido'}


def analizar_contexto(partidos):
    print("[INFO] Analizando contexto ambiental de los partidos...")
    for partido in partidos:
        estadio = partido.get('venue', 'default')
        lat, lon = COORDENADAS_ESTADIOS.get(estadio, COORDENADAS_ESTADIOS['default'])

        clima = obtener_clima(lat, lon)

        try:
            start_time = datetime.strptime(partido['start_time'], "%Y-%m-%dT%H:%M:%S")
            hora_local = start_time.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('US/Eastern')).hour
        except Exception as e:
            print(f"[ERROR] Al convertir hora del partido: {e}")
            hora_local = 19  # Asumimos juego nocturno si falla

        partido['contexto'] = {
            'estadio': estadio,
            'hora_local': hora_local,
            'clima': clima
        }

        print(f"[DEBUG] Contexto {partido['home_team']} vs {partido['away_team']}: {clima} @ {hora_local}h")

    return partidos
