# analysis/statcast.py
#
# Carga estadísticas avanzadas de Fangraphs via pybaseball:
#
#   Pitching por equipo:  xFIP, Barrel% permitido, HardHit%, FIP, K%, BB%
#   Batting por equipo:   Barrel%, HardHit%, wRC+, OPS, K%, BB%
#
# Ambas tablas se cachean en disco 24h para no hacer scraping en cada ejecución.

import json
import os
from datetime import datetime

import pybaseball as pb

pb.cache.enable()

_CACHE_PITCH = "output/fg_pitching_cache.json"
_CACHE_BAT   = "output/fg_batting_cache.json"
_TTL_HORAS   = 24

_PITCH_COLS = ['Team', 'xFIP', 'Barrel%', 'HardHit%', 'ERA', 'FIP', 'WHIP', 'K%', 'BB%']
_BAT_COLS   = ['Team', 'Barrel%', 'HardHit%', 'wRC+', 'OPS', 'AVG', 'K%', 'BB%']

PITCH_DEFAULTS = {
    'xFIP': 4.20, 'Barrel%': 8.0, 'HardHit%': 38.0,
    'ERA': 4.20, 'FIP': 4.20, 'WHIP': 1.28, 'K%': 22.0, 'BB%': 8.5,
}
BAT_DEFAULTS = {
    'Barrel%': 8.0, 'HardHit%': 38.0,
    'wRC+': 100.0, 'OPS': 0.730, 'AVG': 0.250, 'K%': 22.0, 'BB%': 8.5,
}

# Nombres MLB statsapi → abreviatura Fangraphs
_MLB_A_FG = {
    "Arizona Diamondbacks":  "ARI", "Atlanta Braves":        "ATL",
    "Baltimore Orioles":     "BAL", "Boston Red Sox":        "BOS",
    "Chicago Cubs":          "CHC", "Chicago White Sox":     "CWS",
    "Cincinnati Reds":       "CIN", "Cleveland Guardians":   "CLE",
    "Colorado Rockies":      "COL", "Detroit Tigers":        "DET",
    "Houston Astros":        "HOU", "Kansas City Royals":    "KC",
    "Los Angeles Angels":    "LAA", "Los Angeles Dodgers":   "LAD",
    "Miami Marlins":         "MIA", "Milwaukee Brewers":     "MIL",
    "Minnesota Twins":       "MIN", "New York Mets":         "NYM",
    "New York Yankees":      "NYY", "Oakland Athletics":     "OAK",
    "Athletics":             "OAK", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates":    "PIT", "San Diego Padres":      "SD",
    "San Francisco Giants":  "SF",  "Seattle Mariners":      "SEA",
    "St. Louis Cardinals":   "STL", "Tampa Bay Rays":        "TB",
    "Texas Rangers":         "TEX", "Toronto Blue Jays":     "TOR",
    "Washington Nationals":  "WSH",
}


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


def _safe(val, default: float) -> float:
    try:
        v = float(val)
        return default if v != v else v  # NaN → default
    except (TypeError, ValueError):
        return default


def _descargar_pitching(season: int) -> dict:
    try:
        df = pb.fg_team_pitching_data(
            start_season=season, end_season=season,
            stat_columns=_PITCH_COLS,
        )
        out = {}
        for _, row in df.iterrows():
            team = str(row.get('Team', '')).strip()
            if not team:
                continue
            out[team] = {k: _safe(row.get(k), PITCH_DEFAULTS[k]) for k in PITCH_DEFAULTS}
        print(f"[STATCAST] Pitching descargado: {len(out)} equipos.")
        return out
    except Exception as e:
        print(f"[WARNING] Pitching Fangraphs falló: {e}")
        return {}


def _descargar_batting(season: int) -> dict:
    try:
        df = pb.fg_team_batting_data(
            start_season=season, end_season=season,
            stat_columns=_BAT_COLS,
        )
        out = {}
        for _, row in df.iterrows():
            team = str(row.get('Team', '')).strip()
            if not team:
                continue
            out[team] = {k: _safe(row.get(k), BAT_DEFAULTS[k]) for k in BAT_DEFAULTS}
        print(f"[STATCAST] Batting descargado: {len(out)} equipos.")
        return out
    except Exception as e:
        print(f"[WARNING] Batting Fangraphs falló: {e}")
        return {}


# ── estado en memoria (se llena en cargar_statcast) ───────────────────────────
_PITCH_DATA: dict = {}
_BAT_DATA:   dict = {}


def cargar_statcast(season: int = None, forzar: bool = False):
    """Llama una vez al inicio del pipeline en main.py."""
    global _PITCH_DATA, _BAT_DATA
    if season is None:
        season = datetime.now().year

    if not forzar and _cache_ok(_CACHE_PITCH):
        _PITCH_DATA = _leer(_CACHE_PITCH)
        print(f"[STATCAST] Pitching desde caché ({len(_PITCH_DATA)} equipos).")
    else:
        _PITCH_DATA = _descargar_pitching(season)
        if _PITCH_DATA:
            _guardar(_CACHE_PITCH, _PITCH_DATA)

    if not forzar and _cache_ok(_CACHE_BAT):
        _BAT_DATA = _leer(_CACHE_BAT)
        print(f"[STATCAST] Batting desde caché ({len(_BAT_DATA)} equipos).")
    else:
        _BAT_DATA = _descargar_batting(season)
        if _BAT_DATA:
            _guardar(_CACHE_BAT, _BAT_DATA)


def _buscar(data: dict, team_name: str, defaults: dict) -> dict:
    abbr = _MLB_A_FG.get(team_name, "")
    if abbr in data:
        return data[abbr]
    # fallback por coincidencia parcial
    for k, v in data.items():
        if abbr and abbr.lower() in k.lower():
            return v
    return dict(defaults)


def get_pitching(team_name: str) -> dict:
    return _buscar(_PITCH_DATA, team_name, PITCH_DEFAULTS)


def get_batting(team_name: str) -> dict:
    return _buscar(_BAT_DATA, team_name, BAT_DEFAULTS)