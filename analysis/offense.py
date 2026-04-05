# analysis/offense.py
#
# Calcula stats ofensivas del equipo ponderando los primeros N bateadores
# por plate appearances (proxy del batting order) en lugar del promedio
# del equipo completo.
#
# Flujo por equipo:
#   1. Obtener top N_BATEADORES por PA via endpoint 'stats' (1 llamada)
#   2. Para cada bateador, obtener split vsRHP o vsLHP via person hydrate
#   3. Ponderar OPS y AVG por PA de cada bateador
#   4. Si fallan los splits individuales → fallback a stats del equipo completo
#
# Caché en disco de TTL_HORAS para no repetir en la misma ejecución del día.

import json
import os
from datetime import datetime

from statsapi import lookup_team, get
from utils.logger import get as get_log

log = get_log()

# ── Configuración ──────────────────────────────────────────────────────────────
N_BATEADORES  = 5       # corazón del lineup (posiciones 1-5 aprox.)
TTL_HORAS     = 6       # caché en disco
IP_MINIMO_PA  = 50      # PA mínimos para considerar a un bateador
CACHE_DIR     = "output"
CACHE_FILE    = os.path.join(CACHE_DIR, "offense_cache.json")

# Promedios de liga para fallback y normalización
OPS_LIGA_R    = 0.730
OPS_LIGA_L    = 0.710
AVG_LIGA      = 0.250
RPG_LIGA      = 4.50

DEFAULTS_VS_R = {'runsPerGame': 4.50, 'OPS': OPS_LIGA_R, 'wRC+': 100, 'runs_last_5': 4.50}
DEFAULTS_VS_L = {'runsPerGame': 4.30, 'OPS': OPS_LIGA_L, 'wRC+':  96, 'runs_last_5': 4.30}


# ── Caché en disco ─────────────────────────────────────────────────────────────

def _cache_ok() -> bool:
    if not os.path.exists(CACHE_FILE):
        return False
    edad = (datetime.now().timestamp() - os.path.getmtime(CACHE_FILE)) / 3600
    return edad < TTL_HORAS


def _leer_cache() -> dict:
    with open(CACHE_FILE, encoding='utf-8') as f:
        return json.load(f)


def _guardar_cache(data: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


# Estado en memoria para la sesión actual
_CACHE_MEM: dict = {}
_CACHE_CARGADO = False


def _cargar_cache_si_vigente():
    global _CACHE_MEM, _CACHE_CARGADO
    if not _CACHE_CARGADO and _cache_ok():
        try:
            _CACHE_MEM = _leer_cache()
            log.debug(f"Offense caché cargado ({len(_CACHE_MEM)} equipos).")
        except Exception:
            _CACHE_MEM = {}
    _CACHE_CARGADO = True


def _guardar_en_cache(team_name: str, vs_hand: str, resultado: dict):
    clave = f"{team_name}|{vs_hand}"
    _CACHE_MEM[clave] = resultado
    try:
        _guardar_cache(_CACHE_MEM)
    except Exception:
        pass  # caché es opcional — no interrumpir el pipeline


# ── Obtención de datos ─────────────────────────────────────────────────────────

def _safe(val, default: float, lo: float = -999, hi: float = 999) -> float:
    try:
        v = float(val)
        return default if (v != v or v < lo or v > hi) else v
    except (TypeError, ValueError):
        return default


def _top_bateadores(team_id: int, season: int) -> list:
    """
    Devuelve lista de dicts con los top N_BATEADORES bateadores del equipo
    ordenados por PA descendente. Cada dict: {id, pa, ops, obp, slg, avg}.
    """
    try:
        data    = get('stats', {
            'stats':      'season',
            'group':      'hitting',
            'teamId':     team_id,
            'season':     season,
            'playerPool': 'All',
            'limit':      N_BATEADORES * 3,   # pedir más para filtrar por PA
            'sortStat':   'plateAppearances',
            'order':      'desc',
        })
        splits  = data.get('stats', [{}])[0].get('splits', [])
        result  = []
        for s in splits:
            stat   = s.get('stat', {})
            person = s.get('player', {})
            pa     = int(stat.get('plateAppearances', 0) or 0)
            if pa < IP_MINIMO_PA:
                continue
            result.append({
                'id':  person.get('id'),
                'pa':  pa,
                'ops': _safe(stat.get('ops'),          0.730, 0.3, 1.3),
                'obp': _safe(stat.get('obp'),          0.315, 0.1, 0.6),
                'slg': _safe(stat.get('sluggingPct'),  0.415, 0.1, 0.9),
                'avg': _safe(stat.get('avg'),          0.250, 0.0, 0.5),
            })
            if len(result) == N_BATEADORES:
                break
        return result
    except Exception as e:
        log.debug(f"top_bateadores falló (team_id={team_id}): {e}")
        return []


def _split_bateador(player_id: int, vs_hand: str, season: int) -> dict | None:
    """
    Obtiene el split vsRHP o vsLHP de un bateador individual.
    Retorna dict con ops/obp/slg/avg o None si falla.
    """
    sit_code = 'vr' if vs_hand == 'R' else 'vl'
    hydrate  = (f"stats(group=hitting,type=statSplits,"
                f"sitCodes={sit_code},season={season},sportId=1)")
    try:
        data    = get('person', {'personId': player_id, 'hydrate': hydrate})
        persona = data.get('people', [{}])[0]
        for sg in persona.get('stats', []):
            for split in sg.get('splits', []):
                stat = split.get('stat', {})
                ops  = _safe(stat.get('ops'), -1, 0.1, 1.5)
                if ops < 0:
                    continue
                return {
                    'ops': ops,
                    'obp': _safe(stat.get('obp'),         0.315, 0.1, 0.6),
                    'slg': _safe(stat.get('sluggingPct'), 0.415, 0.1, 0.9),
                    'avg': _safe(stat.get('avg'),         0.250, 0.0, 0.5),
                }
    except Exception as e:
        log.debug(f"split_bateador falló (id={player_id}, {vs_hand}): {e}")
    return None


def _ops_ponderado_lineup(bateadores: list, vs_hand: str, season: int) -> dict | None:
    """
    Calcula OPS y AVG ponderados por PA de los bateadores del corazón del lineup.
    Para cada bateador intenta obtener el split específico vs la mano del pitcher.
    Si el split falla, usa las stats generales del bateador como fallback.

    Devuelve dict con ops_pond, avg_pond, n_con_split, n_total
    o None si no hay datos suficientes.
    """
    ops_sum = 0.0
    pa_total = 0

    n_con_split  = 0
    n_total      = len(bateadores)

    for bat in bateadores:
        pid = bat.get('id')
        pa  = bat.get('pa', 0)

        split = _split_bateador(pid, vs_hand, season) if pid else None

        if split:
            ops_usar = split['ops']
            n_con_split += 1
        else:
            ops_usar = bat['ops']   # fallback a stats generales

        ops_sum  += ops_usar * pa
        pa_total += pa

    if pa_total == 0:
        return None

    ops_pond = round(ops_sum / pa_total, 3)
    return {
        'ops_pond':   ops_pond,
        'n_con_split': n_con_split,
        'n_total':     n_total,
    }


def _runs_recientes(team_id: int, n: int = 10) -> float:
    """Promedio de carreras anotadas en los últimos n juegos del schedule."""
    try:
        import numpy as np
        from datetime import timedelta
        from statsapi import schedule
        hoy  = datetime.now().strftime('%Y-%m-%d')
        hace = (datetime.now() - timedelta(days=25)).strftime('%Y-%m-%d')
        juegos = schedule(start_date=hace, end_date=hoy, teamId=team_id)
        runs = []
        for j in juegos:
            if j.get('status') not in ('Final', 'Game Over'):
                continue
            if str(j.get('home_id')) == str(team_id):
                runs.append(int(j.get('home_score', 0) or 0))
            else:
                runs.append(int(j.get('away_score', 0) or 0))
        runs = runs[-n:]
        return round(float(np.mean(runs)), 3) if runs else RPG_LIGA
    except Exception:
        return RPG_LIGA


def _wrc_plus_aprox(ops: float) -> float:
    """wRC+ aproximado desde OPS (proxy sin Fangraphs)."""
    return round(max(50.0, min((ops / 0.730) * 100, 175.0)), 1)


# ── Función principal ──────────────────────────────────────────────────────────

def obtener_stats_ofensivas(team_name: str, vs_hand: str = 'R',
                             season: int = 2025) -> dict:
    """
    Punto de entrada. Devuelve stats ofensivas del equipo ponderando
    el OPS de los primeros N_BATEADORES por PA.
    """
    _cargar_cache_si_vigente()
    clave = f"{team_name}|{vs_hand}"

    if clave in _CACHE_MEM:
        return _CACHE_MEM[clave]

    defaults = dict(DEFAULTS_VS_L if vs_hand == 'L' else DEFAULTS_VS_R)

    try:
        team_id = lookup_team(team_name)[0]['id']
    except Exception:
        _guardar_en_cache(team_name, vs_hand, defaults)
        return defaults

    # Carreras recientes (siempre desde schedule — más confiable)
    runs_recientes = _runs_recientes(team_id, n=10)

    # Top bateadores por PA → OPS ponderado con splits
    bateadores = _top_bateadores(team_id, season)

    if bateadores:
        pond = _ops_ponderado_lineup(bateadores, vs_hand, season)
    else:
        pond = None

    if pond and pond['ops_pond'] > 0:
        ops_final = pond['ops_pond']
        log.debug(
            f"Offense {team_name} vs{'RHP' if vs_hand=='R' else 'LHP'}: "
            f"OPS pond.={ops_final} "
            f"({pond['n_con_split']}/{pond['n_total']} con split)"
        )
    else:
        # Fallback: stats del equipo completo via team_stats
        try:
            sit_code = 'vr' if vs_hand == 'R' else 'vl'
            data     = get('team_stats', {
                'teamId':   team_id,
                'stats':    'statSplits',
                'sitCodes': sit_code,
                'group':    'hitting',
                'season':   season,
            })
            splits = data.get('stats', [{}])[0].get('splits', [])
            stat   = splits[0].get('stat', {}) if splits else {}
            ops_final = _safe(stat.get('ops'), defaults['OPS'], 0.4, 1.2)
        except Exception:
            ops_final = defaults['OPS']
        log.debug(
            f"Offense {team_name} vs{'RHP' if vs_hand=='R' else 'LHP'}: "
            f"OPS equipo={ops_final} (fallback)"
        )

    resultado = {
        'runsPerGame': round(runs_recientes, 3),
        'OPS':         round(ops_final, 3),
        'wRC+':        _wrc_plus_aprox(ops_final),
        'runs_last_5': max(runs_recientes, 1.5),
        'split':       f"vs{'RHP' if vs_hand == 'R' else 'LHP'}",
    }

    _guardar_en_cache(team_name, vs_hand, resultado)
    return resultado


# ── Módulo principal llamado por main.py ──────────────────────────────────────

def analizar_ofensiva(partidos: list) -> list:
    season = datetime.now().year

    for partido in partidos:
        home = partido['home_team']
        away = partido['away_team']

        # El lineup home batea contra el abridor visitante
        hand_vs_home = partido['away_stats']['throws']
        # El lineup away batea contra el abridor local
        hand_vs_away = partido['home_stats']['throws']

        partido['home_offense'] = obtener_stats_ofensivas(home, hand_vs_home, season)
        partido['away_offense'] = obtener_stats_ofensivas(away, hand_vs_away, season)

        log.debug(
            f"OFFENSE {home} ({partido['home_offense']['split']} "
            f"OPS={partido['home_offense']['OPS']} "
            f"R/5={partido['home_offense']['runs_last_5']}) | "
            f"{away} ({partido['away_offense']['split']} "
            f"OPS={partido['away_offense']['OPS']} "
            f"R/5={partido['away_offense']['runs_last_5']})"
        )

    return partidos