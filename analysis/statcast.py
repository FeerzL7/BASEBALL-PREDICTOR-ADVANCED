# analysis/statcast.py
#
# Obtiene estadísticas avanzadas de pitching y bateo por equipo
# usando MLB statsapi (que sí funciona sin bloqueos de región).
#
# FIP aproximado como proxy de xFIP:
#   FIP = (13*HR + 3*BB - 2*K) / IP + constante_liga
#   La constante_liga ajusta FIP para que sea igual a ERA promedio de liga.
#   FIP es prácticamente idéntico a xFIP para muestras de temporada completa.
#
# HardHit% aproximado:
#   Derivado de SLG relativo al promedio de liga. Equipos con SLG alto
#   tienden a hacer contacto más duro. Es un proxy, no el valor exacto
#   de Statcast — pero evita depender de fuentes con restricciones de acceso.

import json
import os
from datetime import datetime

from statsapi import lookup_team, get

_CACHE_PITCH = "output/adv_pitching_cache.json"
_CACHE_BAT   = "output/adv_batting_cache.json"
_TTL_HORAS   = 24

# Constante de liga para FIP 2025 (se acerca a ERA promedio de liga ~4.20)
_FIP_CONSTANTE = 3.10

# Promedios de liga 2025 para normalización
ERA_LIGA        = 4.20
FIP_LIGA        = 4.10
BARREL_PCT_LIGA = 8.0
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

_CACHE: dict = {}


def _cache_ok(path: str) -> bool:
    if not os.path.exists(path):
        return False
    return (datetime.now().timestamp() - os.path.getmtime(path)) / 3600 < _TTL_HORAS


def _guardar(path: str, data: dict):
    os.makedirs("output", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _leer(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe(val, default: float, lo: float = -999, hi: float = 999) -> float:
    try:
        v = float(val)
        if v != v or v < lo or v > hi:
            return default
        return v
    except (TypeError, ValueError):
        return default


def _calcular_fip(stat: dict) -> float:
    """FIP = (13*HR + 3*(BB+HBP) - 2*K) / IP + constante"""
    try:
        hr  = float(stat.get('homeRuns',       0) or 0)
        bb  = float(stat.get('baseOnBalls',    0) or 0)
        hbp = float(stat.get('hitBatsmen',     0) or 0)
        k   = float(stat.get('strikeOuts',     0) or 0)
        ip  = float(stat.get('inningsPitched', 0) or 0)
        if ip < 10:
            return FIP_LIGA
        fip = (13 * hr + 3 * (bb + hbp) - 2 * k) / ip + _FIP_CONSTANTE
        return round(max(1.5, min(fip, 8.0)), 3)
    except Exception:
        return FIP_LIGA


def _hardhit_desde_slg(slg: float) -> float:
    """Proxy de HardHit% basado en SLG relativo al promedio de liga."""
    ratio = slg / SLG_LIGA
    return round(max(20.0, min(HARDHIT_LIGA * ratio, 55.0)), 1)


def _wrc_plus_desde_ops(ops: float, obp: float, slg: float) -> float:
    """
    wRC+ aproximado usando OPS+.
    OPS+ = 100 * (OBP/lgOBP + SLG/lgSLG - 1)
    Es una aproximación, no el wRC+ real de Fangraphs.
    """
    try:
        lg_obp = 0.315
        lg_slg = SLG_LIGA
        ops_plus = 100 * (obp / lg_obp + slg / lg_slg - 1)
        return round(max(50.0, min(ops_plus, 180.0)), 1)
    except Exception:
        return WRC_PLUS_LIGA


def _obtener_stats_equipo(team_name: str, season: int = 2025) -> tuple:
    """Devuelve (pitch_stat_dict, bat_stat_dict) desde MLB statsapi."""
    try:
        team_id = lookup_team(team_name)[0]['id']
    except Exception:
        return {}, {}

    pitch_stat, bat_stat = {}, {}

    try:
        data = get('team_stats', {
            'teamId': team_id, 'group': 'pitching',
            'stats': 'season', 'season': season,
        })
        splits = data.get('stats', [{}])[0].get('splits', [{}])
        pitch_stat = splits[0].get('stat', {}) if splits else {}
    except Exception:
        pass

    try:
        data = get('team_stats', {
            'teamId': team_id, 'group': 'hitting',
            'stats': 'season', 'season': season,
        })
        splits = data.get('stats', [{}])[0].get('splits', [{}])
        bat_stat = splits[0].get('stat', {}) if splits else {}
    except Exception:
        pass

    return pitch_stat, bat_stat


def _procesar_pitching(stat: dict) -> dict:
    if not stat:
        return dict(PITCH_DEFAULTS)
    era  = _safe(stat.get('era'),  ERA_LIGA,  0.5, 9.0)
    whip = _safe(stat.get('whip'), 1.28,      0.5, 3.0)
    fip  = _calcular_fip(stat)
    tbf  = float(stat.get('battersFaced', 0) or 0)
    k    = float(stat.get('strikeOuts',   0) or 0)
    bb   = float(stat.get('baseOnBalls',  0) or 0)
    k_pct  = round(k  / tbf * 100, 1) if tbf > 0 else 22.0
    bb_pct = round(bb / tbf * 100, 1) if tbf > 0 else 8.5
    # HardHit proxy: equipos con ERA alta y WHIP alta tienden a permitir contacto duro
    slg_contra = _safe(stat.get('stolenBasePercentage'), SLG_LIGA, 0.0, 1.0)
    return {
        'FIP':           fip,
        'ERA':           era,
        'WHIP':          whip,
        'K_pct':         max(5.0, min(k_pct, 45.0)),
        'BB_pct':        max(3.0, min(bb_pct, 20.0)),
        'HardHit_aprox': _hardhit_desde_slg(slg_contra if slg_contra > 0.1 else SLG_LIGA),
    }


def _procesar_batting(stat: dict) -> dict:
    if not stat:
        return dict(BAT_DEFAULTS)
    ops = _safe(stat.get('ops'),            OPS_LIGA, 0.4, 1.2)
    slg = _safe(stat.get('sluggingPct'),    SLG_LIGA, 0.2, 0.8)
    obp = _safe(stat.get('obp'),            0.315,    0.2, 0.6)
    pa  = float(stat.get('plateAppearances', 0) or 0)
    k   = float(stat.get('strikeOuts',       0) or 0)
    bb  = float(stat.get('baseOnBalls',      0) or 0)
    k_pct  = round(k  / pa * 100, 1) if pa > 0 else 22.0
    bb_pct = round(bb / pa * 100, 1) if pa > 0 else 8.5
    return {
        'OPS':           ops,
        'SLG':           slg,
        'wRC_plus_aprox': _wrc_plus_desde_ops(ops, obp, slg),
        'HardHit_aprox': _hardhit_desde_slg(slg),
        'K_pct':         max(5.0, min(k_pct, 45.0)),
        'BB_pct':        max(3.0, min(bb_pct, 20.0)),
    }


# ── API pública ───────────────────────────────────────────────────────────────

_PITCH_DATA: dict = {}
_BAT_DATA:   dict = {}


def cargar_statcast(season: int = None, forzar: bool = False):
    """Carga stats avanzadas de todos los equipos vía MLB statsapi."""
    global _PITCH_DATA, _BAT_DATA

    if season is None:
        season = datetime.now().year

    if not forzar and _cache_ok(_CACHE_PITCH) and _cache_ok(_CACHE_BAT):
        _PITCH_DATA = _leer(_CACHE_PITCH)
        _BAT_DATA   = _leer(_CACHE_BAT)
        print(f"[STATCAST] Stats avanzadas desde caché "
              f"({len(_PITCH_DATA)} equipos pitching, {len(_BAT_DATA)} batting).")
        return

    print(f"[STATCAST] Calculando FIP y stats avanzadas via MLB API ({season})...")

    # Lista de todos los equipos MLB
    from statsapi import get as mlb_get
    try:
        teams_data = mlb_get('teams', {'sportId': 1, 'season': season})
        equipos = [(t['name'], t['id']) for t in teams_data.get('teams', [])]
    except Exception:
        equipos = []

    nuevos_pitch, nuevos_bat = {}, {}
    for nombre, _ in equipos:
        pitch_stat, bat_stat = _obtener_stats_equipo(nombre, season)
        nuevos_pitch[nombre] = _procesar_pitching(pitch_stat)
        nuevos_bat[nombre]   = _procesar_batting(bat_stat)

    if nuevos_pitch:
        _PITCH_DATA = nuevos_pitch
        _guardar(_CACHE_PITCH, _PITCH_DATA)
    if nuevos_bat:
        _BAT_DATA = nuevos_bat
        _guardar(_CACHE_BAT, _BAT_DATA)

    print(f"[STATCAST] {len(_PITCH_DATA)} equipos cargados. "
          f"Ejemplo NYY: FIP={_PITCH_DATA.get('New York Yankees', {}).get('FIP', '?')}")


def get_pitching(team_name: str) -> dict:
    if team_name in _PITCH_DATA:
        return _PITCH_DATA[team_name]
    # Fallback por coincidencia parcial
    for k, v in _PITCH_DATA.items():
        if team_name.lower() in k.lower() or k.lower() in team_name.lower():
            return v
    return dict(PITCH_DEFAULTS)


def get_batting(team_name: str) -> dict:
    if team_name in _BAT_DATA:
        return _BAT_DATA[team_name]
    for k, v in _BAT_DATA.items():
        if team_name.lower() in k.lower() or k.lower() in team_name.lower():
            return v
    return dict(BAT_DEFAULTS)