# analysis/bullpen.py
#
# Obtiene ERA y WHIP del bullpen de cada equipo.
# Estrategia: consulta team_roster (endpoint correcto en MLB-StatsAPI)
# para obtener los pitchers activos, luego person_stats por cada uno,
# filtra relievers y calcula promedio ponderado por IP.

from statsapi import lookup_team, get

_CACHE = {}

DEFAULTS = {'ERA': 4.20, 'WHIP': 1.28, 'IP': 0.0}


def _stats_bullpen(team_id: int, season: int = 2025) -> dict:
    # 1. Obtener roster activo con el endpoint correcto: team_roster
    try:
        data = get('team_roster', {
            'teamId':     team_id,
            'rosterType': 'active',
            'season':     season,
        })
        roster = data.get('roster', [])
    except Exception as e:
        print(f"[WARNING] team_roster falló (team_id={team_id}): {e}")
        return dict(DEFAULTS)

    # Filtrar solo pitchers por abreviatura de posición
    pitcher_ids = [
        p['person']['id']
        for p in roster
        if p.get('position', {}).get('abbreviation') == 'P'
    ]

    if not pitcher_ids:
        return dict(DEFAULTS)

    era_sum  = 0.0
    whip_sum = 0.0
    ip_total = 0.0

    for pid in pitcher_ids:
        try:
            # person_stats es el endpoint correcto para stats individuales
            s = get('person_stats', {
                'personId': pid,
                'stats':    'season',
                'group':    'pitching',
                'season':   season,
            })
            splits = s.get('stats', [{}])[0].get('splits', [])
            if not splits:
                continue
            stat = splits[0].get('stat', {})

            ip     = float(stat.get('inningsPitched', 0) or 0)
            era    = float(stat.get('era',  4.50) or 4.50)
            whip   = float(stat.get('whip', 1.30) or 1.30)
            games  = int(stat.get('gamesPlayed',  0) or 0)
            gs     = int(stat.get('gamesStarted', 0) or 0)

            # Solo relievers: al menos 3 IP, y aperturas < 30% de salidas
            if ip < 3 or (games > 0 and gs / games >= 0.3):
                continue

            era_sum  += era  * ip
            whip_sum += whip * ip
            ip_total += ip

        except Exception:
            continue

    if ip_total == 0:
        return dict(DEFAULTS)

    return {
        'ERA':  round(era_sum  / ip_total, 3),
        'WHIP': round(whip_sum / ip_total, 3),
        'IP':   round(ip_total, 1),
    }


def obtener_bullpen(team_name: str, season: int = 2025) -> dict:
    """Punto de entrada público. Cachea por equipo."""
    key = (team_name.lower(), season)
    if key in _CACHE:
        return _CACHE[key]

    try:
        team_id = lookup_team(team_name)[0]['id']
    except Exception:
        _CACHE[key] = dict(DEFAULTS)
        return _CACHE[key]

    result = _stats_bullpen(team_id, season)
    _CACHE[key] = result
    print(
        f"[BULLPEN] {team_name}: ERA={result['ERA']} "
        f"WHIP={result['WHIP']} IP={result['IP']}"
    )
    return result


def limpiar_cache():
    _CACHE.clear()