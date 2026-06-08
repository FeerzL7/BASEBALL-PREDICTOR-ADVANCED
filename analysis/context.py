# analysis/context.py
import requests
from datetime import datetime
import pytz
from utils.logger import get as get_log

log = get_log()

COORDENADAS_ESTADIOS = {
    'Angel Stadium':               (33.8003, -117.8827),
    'Busch Stadium':               (38.6226,  -90.1928),
    'Camden Yards':                (39.2840,  -76.6217),
    'Chase Field':                 (33.4455, -112.0667),
    'Citi Field':                  (40.7571,  -73.8458),
    'Citizens Bank Park':          (39.9061,  -75.1665),
    'Comerica Park':               (42.3390,  -83.0485),
    'Coors Field':                 (39.7559, -104.9942),
    'Dodger Stadium':              (34.0739, -118.2390),
    'Fenway Park':                 (42.3467,  -71.0972),
    'Globe Life Field':            (32.7473,  -97.0847),
    'Great American Ball Park':    (39.0979,  -84.5082),
    'Guaranteed Rate Field':       (41.8300,  -87.6339),
    'Kauffman Stadium':            (39.0517,  -94.4803),
    'loanDepot park':              (25.7781,  -80.2197),
    'Minute Maid Park':            (29.7573,  -95.3555),
    'Nationals Park':              (38.8730,  -77.0074),
    'Oakland Coliseum':            (37.7516, -122.2005),
    'Oracle Park':                 (37.7786, -122.3893),
    'Petco Park':                  (32.7076, -117.1570),
    'PNC Park':                    (40.4469,  -80.0057),
    'Progressive Field':           (41.4962,  -81.6852),
    'Rogers Centre':               (43.6414,  -79.3894),
    'T-Mobile Park':               (47.5914, -122.3325),
    'Target Field':                (44.9817,  -93.2776),
    'Tropicana Field':             (27.7682,  -82.6534),
    'Truist Park':                 (33.8908,  -84.4678),
    'Wrigley Field':               (41.9484,  -87.6553),
    'Yankee Stadium':              (40.8296,  -73.9262),
    'American Family Field':       (43.0280,  -87.9712),
    'default':                     (40.0,    -100.0),
}

CLIMA_CODES = {
    0: 'Despejado', 1: 'Principalmente despejado', 2: 'Parcialmente nublado',
    3: 'Nublado', 45: 'Niebla', 51: 'Llovizna ligera',
    61: 'Lluvia moderada', 71: 'Nieve ligera', 95: 'Tormenta',
}

TIMEZONE_ESTADIOS = {
    'Angel Stadium': 'US/Pacific',
    'Chase Field': 'US/Arizona',
    'Coors Field': 'US/Mountain',
    'Dodger Stadium': 'US/Pacific',
    'Globe Life Field': 'US/Central',
    'Guaranteed Rate Field': 'US/Central',
    'Kauffman Stadium': 'US/Central',
    'Minute Maid Park': 'US/Central',
    'Oakland Coliseum': 'US/Pacific',
    'Oracle Park': 'US/Pacific',
    'Petco Park': 'US/Pacific',
    'T-Mobile Park': 'US/Pacific',
    'Target Field': 'US/Central',
    'American Family Field': 'US/Central',
    'Busch Stadium': 'US/Central',
    'Wrigley Field': 'US/Central',
}

DEFAULT_TZ = 'US/Eastern'


def _parse_utc(value: str) -> datetime | None:
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.utc)
    except Exception:
        return None


def _valor_horario(hourly: dict, key: str, idx: int, default):
    values = hourly.get(key) or []
    if idx < len(values):
        return values[idx]
    return default


def obtener_clima(lat, lon, start_time: str | None = None):
    inicio_utc = _parse_utc(start_time or "")
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": "true",
            "timezone": "UTC",
        }
        if inicio_utc:
            fecha = inicio_utc.strftime("%Y-%m-%d")
            params.update({
                "hourly": "temperature_2m,windspeed_10m,weathercode",
                "start_date": fecha,
                "end_date": fecha,
            })

        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        hourly = data.get("hourly") or {}
        times = hourly.get("time") or []
        if inicio_utc and times:
            objetivo = inicio_utc.replace(minute=0, second=0, microsecond=0)
            horas = [_parse_utc(t) for t in times]
            validas = [(i, h) for i, h in enumerate(horas) if h is not None]
            if validas:
                idx, _ = min(validas, key=lambda item: abs(item[1] - objetivo))
                code = _valor_horario(hourly, "weathercode", idx, None)
                return {
                    'temperatura': _valor_horario(hourly, "temperature_2m", idx, 22),
                    'viento_kph':  _valor_horario(hourly, "windspeed_10m", idx, 10),
                    'condiciones': CLIMA_CODES.get(code, 'desconocido'),
                    'fuente':      'open-meteo-hourly',
                    'is_default':  False,
                }

        clima = data.get('current_weather', {})
        return {
            'temperatura': clima.get('temperature', 22),
            'viento_kph':  clima.get('windspeed', 10),
            'condiciones': CLIMA_CODES.get(clima.get('weathercode'), 'desconocido'),
            'fuente':      'open-meteo-current',
            'is_default':  False,
        }
    except Exception as e:
        log.warning(f"Error obteniendo clima: {e}")
        return {
            'temperatura': 22,
            'viento_kph': 10,
            'condiciones': 'desconocido',
            'fuente': 'default',
            'is_default': True,
        }


def analizar_contexto(partidos):
    log.debug("Analizando contexto ambiental...")
    for partido in partidos:
        estadio    = partido.get('venue_name') or partido.get('venue') or 'default'
        usa_default = estadio not in COORDENADAS_ESTADIOS
        lat, lon   = COORDENADAS_ESTADIOS.get(estadio, COORDENADAS_ESTADIOS['default'])
        clima      = obtener_clima(lat, lon, partido.get('start_time'))
        clima['venue_default'] = usa_default

        if usa_default:
            log.warning(f"Estadio sin coordenadas: {estadio}. Usando coordenada default.")

        try:
            start_time = datetime.strptime(partido['start_time'], "%Y-%m-%dT%H:%M:%S")
            tz_name = TIMEZONE_ESTADIOS.get(estadio, DEFAULT_TZ)
            hora_local = (start_time.replace(tzinfo=pytz.utc)
                          .astimezone(pytz.timezone(tz_name)).hour)
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
