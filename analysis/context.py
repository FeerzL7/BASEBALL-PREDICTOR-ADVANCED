# analysis/context.py
import requests
from datetime import datetime
import pytz
from utils.logger import get as get_log

log = get_log()

COORDENADAS_ESTADIOS = {
    'Coors Field':              (39.7559, -104.9942),
    'Fenway Park':              (42.3467,  -71.0972),
    'Dodger Stadium':           (34.0739, -118.2390),
    'Petco Park':               (32.7076, -117.1570),
    'Yankee Stadium':           (40.8296,  -73.9262),
    'Globe Life Field':         (32.7473,  -97.0847),
    'Oakland Coliseum':         (37.7516, -122.2005),
    'default':                  (40.0,    -100.0),
}

CLIMA_CODES = {
    0: 'Despejado', 1: 'Principalmente despejado', 2: 'Parcialmente nublado',
    3: 'Nublado', 45: 'Niebla', 51: 'Llovizna ligera',
    61: 'Lluvia moderada', 71: 'Nieve ligera', 95: 'Tormenta',
}


def obtener_clima(lat, lon):
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": "true"},
            timeout=10,
        )
        clima = resp.json().get('current_weather', {})
        return {
            'temperatura': clima.get('temperature', 22),
            'viento_kph':  clima.get('windspeed', 10),
            'condiciones': CLIMA_CODES.get(clima.get('weathercode'), 'desconocido'),
        }
    except Exception as e:
        log.warning(f"Error obteniendo clima: {e}")
        return {'temperatura': 22, 'viento_kph': 10, 'condiciones': 'desconocido'}


def analizar_contexto(partidos):
    log.debug("Analizando contexto ambiental...")
    for partido in partidos:
        estadio    = partido.get('venue', 'default')
        lat, lon   = COORDENADAS_ESTADIOS.get(estadio, COORDENADAS_ESTADIOS['default'])
        clima      = obtener_clima(lat, lon)

        try:
            start_time = datetime.strptime(partido['start_time'], "%Y-%m-%dT%H:%M:%S")
            hora_local = (start_time.replace(tzinfo=pytz.utc)
                          .astimezone(pytz.timezone('US/Eastern')).hour)
        except Exception:
            hora_local = 19

        partido['contexto'] = {
            'estadio':    estadio,
            'hora_local': hora_local,
            'clima':      clima,
        }
        log.debug(
            f"Contexto {partido['home_team']} vs {partido['away_team']}: "
            f"{clima} @ {hora_local}h"
        )

    return partidos