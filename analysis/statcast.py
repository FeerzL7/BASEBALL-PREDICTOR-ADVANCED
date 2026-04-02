# analysis/statcast.py
import json
import os
from datetime import datetime

from statsapi import lookup_team, get
from utils.logger import get as get_log

log = get_log()

_CACHE_PITCH = "output/adv_pitching_cache.json"
_CACHE_BAT   = "output/adv_batting_cache.json"
_TTL_HORAS   = 24

_FIP_CONSTANTE  = 3.10
ERA_LIGA        = 4.20
FIP_LIGA        = 4.10
HARDHIT_LIGA    = 38.0
WRC_PLUS_LIGA   = 100.0
SLG_LIGA        = 0.415
OPS_LIGA        = 0.730

PITCH_DEFAULTS = {
    'FIP': 4.10, 'ERA': 4.20, 'WHIP': 1.28,
    'K_pct': 22.0, 'BB_pct': 8.5, 'HardHit_aprox': 38.0,
}
BAT_DEFAULTS = {
    'OPS': 0.730, 'SLG': 0.415, 'wRC_plus_aprox': 100.0,
    'HardHit_aprox': 38.0, 'K_pct': 22.0, 'BB_pct': 8.5,
}


def _cache_ok(path):
    if not os.path.exists(path):
        return False
    return (datetime.now().timestamp() - os.path.getmtime(path)) / 3600 < _TTL_HORAS


def _guardar(path, data):
    os.makedirs("output", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _leer(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe(val, default, lo=-999, hi=999):
    try:
        v = float(val)
        return default if (v != v or v < lo or v > hi) else v
    except (TypeError, ValueError):
        return default


def _calcular_fip(stat):
    try:
        hr  = float(stat.get('homeRuns',       0) or 0)
        bb  = float(stat.get('baseOnBalls',    0) or 0)
        hbp = float(stat.get('hitBatsmen',     0) or 0)
        k   = float(stat.get('strikeOuts',     0) or 0)
        ip  = float(stat.get('inningsPitched', 0) or 0)
        if ip < 10:
            return FIP_LIGA
        return round(max(1.5, min((13*hr + 3*(bb+hbp) - 2*k) / ip + _FIP_CONSTANTE, 8.0)), 3)
    except Exception:
        return FIP_LIGA


def _hardhit_desde_slg(slg):
    return round(max(20.0, min(HARDHIT_LIGA * (slg / SLG_LIGA), 55.0)), 1)


def _wrc_plus_desde_ops(ops, obp, slg):
    try:
        return round(max(50.0, min(100 * (obp / 0.315 + slg / SLG_LIGA - 1), 180.0)), 1)
    except Exception:
        return WRC_PLUS_LIGA


def _obtener_stats_equipo(team_name, season=2025):
    try:
        team_id = lookup_team(team_name)[0]['id']
    except Exception:
        return {}, {}
    pitch_stat = bat_stat = {}
    for group in ('pitching', 'hitting'):
        try:
            data   = get('team_stats', {
                'teamId': team_id, 'group': group,
                'stats': 'season', 'season': season,
            })
            splits = data.get('stats', [{}])[0].get('splits', [{}])
            stat   = splits[0].get('stat', {}) if splits else {}
            if group == 'pitching':
                pitch_stat = stat
            else:
                bat_stat = stat
        except Exception:
            pass
    return pitch_stat, bat_stat


def _procesar_pitching(stat):
    if not stat:
        return dict(PITCH_DEFAULTS)
    era  = _safe(stat.get('era'),  ERA_LIGA, 0.5, 9.0)
    whip = _safe(stat.get('whip'), 1.28,     0.5, 3.0)
    fip  = _calcular_fip(stat)
    tbf  = float(stat.get('battersFaced', 0) or 0)
    k    = float(stat.get('strikeOuts',   0) or 0)
    bb   = float(stat.get('baseOnBalls',  0) or 0)
    k_pct  = round(k  / tbf * 100, 1) if tbf > 0 else 22.0
    bb_pct = round(bb / tbf * 100, 1) if tbf > 0 else 8.5
    return {
        'FIP':           fip,
        'ERA':           era,
        'WHIP':          whip,
        'K_pct':         max(5.0, min(k_pct,  45.0)),
        'BB_pct':        max(3.0, min(bb_pct, 20.0)),
        'HardHit_aprox': _hardhit_desde_slg(SLG_LIGA),
    }


def _procesar_batting(stat):
    if not stat:
        return dict(BAT_DEFAULTS)
    ops = _safe(stat.get('ops'),         OPS_LIGA, 0.4, 1.2)
    slg = _safe(stat.get('sluggingPct'), SLG_LIGA, 0.2, 0.8)
    obp = _safe(stat.get('obp'),         0.315,    0.2, 0.6)
    pa  = float(stat.get('plateAppearances', 0) or 0)
    k   = float(stat.get('strikeOuts',       0) or 0)
    bb  = float(stat.get('baseOnBalls',      0) or 0)
    k_pct  = round(k  / pa * 100, 1) if pa > 0 else 22.0
    bb_pct = round(bb / pa * 100, 1) if pa > 0 else 8.5
    return {
        'OPS':            ops,
        'SLG':            slg,
        'wRC_plus_aprox': _wrc_plus_desde_ops(ops, obp, slg),
        'HardHit_aprox':  _hardhit_desde_slg(slg),
        'K_pct':          max(5.0, min(k_pct,  45.0)),
        'BB_pct':         max(3.0, min(bb_pct, 20.0)),
    }


_PITCH_DATA: dict = {}
_BAT_DATA:   dict = {}


def cargar_statcast(season=None, forzar=False):
    global _PITCH_DATA, _BAT_DATA
    if season is None:
        season = datetime.now().year

    if not forzar and _cache_ok(_CACHE_PITCH) and _cache_ok(_CACHE_BAT):
        _PITCH_DATA = _leer(_CACHE_PITCH)
        _BAT_DATA   = _leer(_CACHE_BAT)
        log.info(f"Stats avanzadas desde caché "
                 f"({len(_PITCH_DATA)} pitching, {len(_BAT_DATA)} batting).")
        return

    log.info(f"Calculando FIP y stats avanzadas via MLB API ({season})...")
    try:
        from statsapi import get as mlb_get
        teams_data = mlb_get('teams', {'sportId': 1, 'season': season})
        equipos    = [(t['name'], t['id']) for t in teams_data.get('teams', [])]
    except Exception:
        equipos = []

    nuevos_pitch, nuevos_bat = {}, {}
    for nombre, _ in equipos:
        ps, bs = _obtener_stats_equipo(nombre, season)
        nuevos_pitch[nombre] = _procesar_pitching(ps)
        nuevos_bat[nombre]   = _procesar_batting(bs)

    if nuevos_pitch:
        _PITCH_DATA = nuevos_pitch
        _guardar(_CACHE_PITCH, _PITCH_DATA)
    if nuevos_bat:
        _BAT_DATA = nuevos_bat
        _guardar(_CACHE_BAT, _BAT_DATA)

    log.info(f"{len(_PITCH_DATA)} equipos cargados con stats avanzadas.")


def _buscar(data, team_name, defaults):
    if team_name in data:
        return data[team_name]
    for k, v in data.items():
        if team_name.lower() in k.lower() or k.lower() in team_name.lower():
            return v
    return dict(defaults)


def get_pitching(team_name):
    return _buscar(_PITCH_DATA, team_name, PITCH_DEFAULTS)


def get_batting(team_name):
    return _buscar(_BAT_DATA, team_name, BAT_DEFAULTS)