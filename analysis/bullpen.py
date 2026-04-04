# analysis/bullpen.py
#
# Obtiene ERA y WHIP reales del bullpen de cada equipo.
#
# Estrategia:
#   Endpoint 'stats' global con teamId filtra todos los pitchers del equipo
#   en una sola llamada. En Python separamos starters de relievers por:
#     - gamesStarted < gamesPlayed * UMBRAL_STARTER  (rol principal)
#     - inningsPitched >= IP_MINIMO                  (muestra suficiente)
#   Luego calculamos ERA y WHIP ponderados por innings lanzados.
#
# Por qué no usar team_roster + person_stats (versión anterior):
#   team_roster devuelve "Invalid endpoint" en muchos entornos.
#   El endpoint 'stats' global con teamId funciona sin autenticación especial
#   y devuelve todos los pitchers con sus splits en una sola llamada.

from statsapi import lookup_team, get
from utils.logger import get as get_log

log = get_log()

_CACHE: dict = {}

DEFAULTS = {'ERA': 4.20, 'WHIP': 1.28, 'IP': 0.0, 'n_pitchers': 0}

# Un pitcher es starter si arrancó en >= 30% de sus salidas
UMBRAL_STARTER = 0.30

# Mínimo de innings para incluir un pitcher en el promedio del bullpen
IP_MINIMO = 5.0

# Límite de pitchers a descargar por equipo (evita páginas múltiples)
LIMIT_PITCHERS = 40


def _calcular_bullpen(splits: list) -> dict:
    """
    Recibe la lista de splits del endpoint stats global para un equipo,
    filtra relievers y calcula ERA/WHIP ponderados por IP.
    """
    era_sum  = 0.0
    whip_sum = 0.0
    ip_total = 0.0
    n        = 0

    for entry in splits:
        stat = entry.get('stat', {})

        try:
            ip     = float(stat.get('inningsPitched', 0) or 0)
            games  = int(stat.get('gamesPlayed',  0) or 0)
            gs     = int(stat.get('gamesStarted', 0) or 0)
            era    = float(stat.get('era',  4.50) or 4.50)
            whip   = float(stat.get('whip', 1.30) or 1.30)
        except (TypeError, ValueError):
            continue

        # Filtrar: suficientes innings y principalmente relevista
        if ip < IP_MINIMO:
            continue
        if games > 0 and gs / games >= UMBRAL_STARTER:
            continue

        # Clamp para evitar datos corruptos (ERA 0.00 con 5 IP en abril)
        era  = max(0.50, min(era,  12.0))
        whip = max(0.50, min(whip,  4.0))

        era_sum  += era  * ip
        whip_sum += whip * ip
        ip_total += ip
        n        += 1

    if ip_total == 0 or n == 0:
        return dict(DEFAULTS)

    return {
        'ERA':        round(era_sum  / ip_total, 3),
        'WHIP':       round(whip_sum / ip_total, 3),
        'IP':         round(ip_total, 1),
        'n_pitchers': n,
    }


def _obtener_splits_equipo(team_id: int, season: int) -> list:
    """
    Llama al endpoint 'stats' global con teamId para obtener
    todos los pitchers del equipo en una sola request.
    Devuelve la lista de splits o [] si falla.
    """
    try:
        data = get('stats', {
            'stats':      'season',
            'group':      'pitching',
            'teamId':     team_id,
            'season':     season,
            'playerPool': 'All',
            'limit':      LIMIT_PITCHERS,
        })
        # Estructura: data['stats'][0]['splits'] = lista de pitchers
        splits = data.get('stats', [{}])[0].get('splits', [])
        return splits
    except Exception as e:
        log.warning(f"stats global falló (team_id={team_id}): {e}")
        return []


def obtener_bullpen(team_name: str, season: int = 2025) -> dict:
    """
    Punto de entrada público. Cachea por (equipo, temporada)
    para no repetir llamadas durante la misma ejecución.
    """
    key = (team_name.lower(), season)
    if key in _CACHE:
        return _CACHE[key]

    try:
        team_id = lookup_team(team_name)[0]['id']
    except Exception as e:
        log.warning(f"lookup_team falló para '{team_name}': {e}")
        _CACHE[key] = dict(DEFAULTS)
        return _CACHE[key]

    splits = _obtener_splits_equipo(team_id, season)

    if not splits:
        log.warning(f"Sin datos de pitchers para {team_name} — usando defaults.")
        _CACHE[key] = dict(DEFAULTS)
        return _CACHE[key]

    result = _calcular_bullpen(splits)
    _CACHE[key] = result

    if result['n_pitchers'] == 0:
        log.warning(
            f"Bullpen {team_name}: sin relievers con >= {IP_MINIMO} IP "
            f"— usando ERA default."
        )
    else:
        log.debug(
            f"Bullpen {team_name}: ERA={result['ERA']} "
            f"WHIP={result['WHIP']} IP={result['IP']} "
            f"({result['n_pitchers']} relievers)"
        )

    return result


def limpiar_cache():
    """Útil para tests o ejecuciones consecutivas en la misma sesión."""
    _CACHE.clear()