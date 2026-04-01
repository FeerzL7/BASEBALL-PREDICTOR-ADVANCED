# analysis/park_factors.py
#
# Calcula Park Factors dinámicos para la temporada actual usando la API de MLB.
#
# Metodología:
#   PF_equipo = (R_casa/G_casa) / (R_visitante/G_visitante)
#
#   Donde R y G son las carreras anotadas Y permitidas en cada split,
#   divididas entre juegos jugados. Esto captura el efecto del estadio
#   independientemente de la calidad ofensiva del equipo.
#
#   PF > 1.0 → estadio favorece la ofensiva (ej: Coors Field ~1.30)
#   PF < 1.0 → estadio penaliza la ofensiva (ej: Petco Park ~0.92)
#
# Fallback: si la API falla o hay menos de 15 juegos en casa,
# se devuelven los valores históricos de constants.py.

import json
import os
from datetime import datetime

from statsapi import get, lookup_team

# Ruta del caché en disco — se regenera si tiene más de 24h
_CACHE_PATH  = "output/park_factors_cache.json"
_CACHE_TTL_H = 24

# Mínimo de juegos en casa para considerar el dato confiable
_MIN_JUEGOS = 15

# Valores históricos de respaldo (de constants.py)
from utils.constants import PARK_FACTORS as _HISTORICOS


def _cache_vigente() -> bool:
    """Devuelve True si el caché en disco tiene menos de _CACHE_TTL_H horas."""
    if not os.path.exists(_CACHE_PATH):
        return False
    mtime = os.path.getmtime(_CACHE_PATH)
    edad_horas = (datetime.now().timestamp() - mtime) / 3600
    return edad_horas < _CACHE_TTL_H


def _guardar_cache(data: dict):
    os.makedirs("output", exist_ok=True)
    with open(_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _leer_cache() -> dict:
    with open(_CACHE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _obtener_stats_liga(game_type: str, season: int) -> dict:
    """
    Descarga stats de hitting de todos los equipos MLB para un gameType.
    Devuelve dict: team_name → stat_dict
    """
    try:
        data = get("teams_stats", {
            "season":   season,
            "group":    "hitting",
            "gameType": game_type,
            "stats":    "season",
            "sportIds": 1,
        })
        resultado = {}
        for entry in data.get("stats", []):
            for split in entry.get("splits", []):
                team = split.get("team", {})
                nombre = team.get("name", "")
                stat   = split.get("stat", {})
                if nombre and stat:
                    resultado[nombre] = stat
        return resultado
    except Exception as e:
        print(f"[WARNING] park_factors: no se pudo obtener stats gameType={game_type}: {e}")
        return {}


def _nombre_a_venue(team_name: str) -> str:
    """
    Mapea nombre de equipo al nombre de su estadio.
    Usado para aplicar el PF al partido correcto.
    """
    MAPA = {
        "Colorado Rockies":       "Coors Field",
        "Boston Red Sox":         "Fenway Park",
        "Texas Rangers":          "Globe Life Field",
        "Oakland Athletics":      "Oakland Coliseum",
        "Athletics":              "Oakland Coliseum",
        "Los Angeles Dodgers":    "Dodger Stadium",
        "San Diego Padres":       "Petco Park",
        "New York Yankees":       "Yankee Stadium",
        "Chicago Cubs":           "Wrigley Field",
        "San Francisco Giants":   "Oracle Park",
        "Houston Astros":         "Minute Maid Park",
        "Minnesota Twins":        "Target Field",
        "Seattle Mariners":       "T-Mobile Park",
        "Miami Marlins":          "loanDepot park",
        "Tampa Bay Rays":         "Tropicana Field",
        "Baltimore Orioles":      "Camden Yards",
        "Cleveland Guardians":    "Progressive Field",
        "Detroit Tigers":         "Comerica Park",
        "Chicago White Sox":      "Guaranteed Rate Field",
        "Kansas City Royals":     "Kauffman Stadium",
        "Los Angeles Angels":     "Angel Stadium",
        "Arizona Diamondbacks":   "Chase Field",
        "Atlanta Braves":         "Truist Park",
        "Cincinnati Reds":        "Great American Ball Park",
        "Milwaukee Brewers":      "American Family Field",
        "Pittsburgh Pirates":     "PNC Park",
        "St. Louis Cardinals":    "Busch Stadium",
        "New York Mets":          "Citi Field",
        "Philadelphia Phillies":  "Citizens Bank Park",
        "Washington Nationals":   "Nationals Park",
        "Toronto Blue Jays":      "Rogers Centre",
    }
    return MAPA.get(team_name, team_name)


def calcular_park_factors(season: int = None, forzar: bool = False) -> dict:
    """
    Devuelve un dict {venue_name: park_factor} con valores dinámicos.

    - Usa caché en disco si tiene menos de 24h (evita llamadas repetidas).
    - Complementa con valores históricos para estadios sin datos suficientes.
    - Si forzar=True, regenera aunque el caché sea reciente.
    """
    if not forzar and _cache_vigente():
        pf = _leer_cache()
        print(f"[PARK] Usando caché de park factors ({len(pf)} estadios).")
        return pf

    if season is None:
        season = datetime.now().year

    print(f"[PARK] Calculando park factors dinámicos para temporada {season}...")

    # Una sola llamada para casa y otra para visitante — todos los equipos
    stats_home = _obtener_stats_liga("H", season)
    stats_away = _obtener_stats_liga("A", season)

    if not stats_home or not stats_away:
        print("[PARK] No hay datos suficientes de la API. Usando valores históricos.")
        return dict(_HISTORICOS)

    park_factors = {}
    skipped = []

    for team_name, sh in stats_home.items():
        sa = stats_away.get(team_name)
        if not sa:
            skipped.append(team_name)
            continue

        g_home = int(sh.get("gamesPlayed", 0) or 0)
        g_away = int(sa.get("gamesPlayed", 0) or 0)

        # Necesitamos suficientes juegos para que el dato sea estable
        if g_home < _MIN_JUEGOS or g_away < _MIN_JUEGOS:
            skipped.append(f"{team_name} (juegos insuf: {g_home}H/{g_away}A)")
            continue

        # Carreras anotadas + permitidas (ambos lados del juego en ese estadio)
        r_home = int(sh.get("runs", 0) or 0) + int(sh.get("runsAllowed", 0) or 0)
        r_away = int(sa.get("runs", 0) or 0) + int(sa.get("runsAllowed", 0) or 0)

        if r_away == 0 or g_away == 0:
            skipped.append(team_name)
            continue

        tasa_home = r_home / g_home
        tasa_away = r_away / g_away

        pf_raw = tasa_home / tasa_away

        # Suavizar hacia 1.0 con un 20% de regresión a la media
        # (evita valores extremos por pequeña muestra de temporada)
        pf_suavizado = round(0.80 * pf_raw + 0.20 * 1.0, 3)

        venue = _nombre_a_venue(team_name)
        park_factors[venue] = pf_suavizado

    # Complementar con históricos para estadios sin datos dinámicos
    for venue, pf_hist in _HISTORICOS.items():
        if venue not in park_factors and venue != 'default':
            park_factors[venue] = pf_hist

    park_factors['default'] = 1.0

    if skipped:
        print(f"[PARK] Equipos sin datos suficientes ({len(skipped)}): "
              f"{', '.join(skipped[:5])}{'...' if len(skipped) > 5 else ''}")

    print(f"[PARK] {len(park_factors)} park factors calculados.")
    for v, pf in sorted(park_factors.items(), key=lambda x: -x[1]):
        if v != 'default':
            print(f"  {v:<30} {pf:.3f}")

    _guardar_cache(park_factors)
    return park_factors