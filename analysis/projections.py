# analysis/projections.py
from analysis.park_factors import calcular_park_factors
from analysis.statcast import (
    get_pitching, get_batting,
    PITCH_DEFAULTS, BAT_DEFAULTS,
    ERA_LIGA, FIP_LIGA, HARDHIT_LIGA, WRC_PLUS_LIGA, OPS_LIGA,
)

PESO_BULLPEN = 0.33
PESO_ABRIDOR = 1.0 - PESO_BULLPEN

# Clamps de factores multiplicativos — ninguno puede mover la proyección
# más de un 45% en ninguna dirección desde la base
_F_MIN = 0.60
_F_MAX = 1.55

_PARK_FACTORS = None
_PISO_CARRERAS = 2.0   # mínimo absoluto de carreras proyectadas por equipo


def _get_park_factors() -> dict:
    global _PARK_FACTORS
    if _PARK_FACTORS is None:
        _PARK_FACTORS = calcular_park_factors()
    return _PARK_FACTORS


def ajustar_park_factor(base_pf: float, contexto: dict) -> float:
    if not contexto:
        return base_pf
    temp   = contexto.get("clima", {}).get("temperatura", 22)
    viento = contexto.get("clima", {}).get("viento_kph", 10)
    ajuste = 1.0
    if temp   >= 28: ajuste += 0.05
    elif temp <= 15: ajuste -= 0.05
    if viento >= 15: ajuste += 0.05
    if contexto.get("hora_local", 19) >= 20:
        ajuste -= 0.02
    return max(round(base_pf * ajuste, 3), 0.85)


def _era_combinada(starter_era: float, bullpen_era: float) -> float:
    starter_era = max(1.0, min(float(starter_era or ERA_LIGA), 9.0))
    bullpen_era = max(1.0, min(float(bullpen_era or ERA_LIGA), 9.0))
    return round(starter_era * PESO_ABRIDOR + bullpen_era * PESO_BULLPEN, 3)


def _clamp(v: float) -> float:
    return max(_F_MIN, min(v, _F_MAX))


def _f_pitcheo(starter_era: float, bullpen_era: float, fip: float) -> float:
    """
    Factor de pitcheo rival combinado.
    ERA alta → lineup anota más (factor > 1).
    FIP bajo → pitcher mejor de lo que parece por ERA (modera hacia abajo).
    Pesos: 55% ERA combinada, 45% FIP
    """
    era_comb = _era_combinada(starter_era, bullpen_era)
    fip      = max(2.0, min(fip, 7.0))

    f_era = era_comb / ERA_LIGA
    f_fip = fip / FIP_LIGA

    return _clamp(f_era * 0.55 + f_fip * 0.45)


def _f_lineup(ops: float, wrc_aprox: float) -> float:
    """Calidad ofensiva del lineup: promedio de OPS y wRC+ normalizados."""
    ops      = max(0.50, min(ops, 1.10))
    wrc_aprox = max(50.0, min(wrc_aprox, 170.0))
    f_ops = ops / OPS_LIGA
    f_wrc = wrc_aprox / WRC_PLUS_LIGA
    return _clamp((f_ops + f_wrc) / 2.0)


def proyectar_carreras(
    ofensiva: dict,
    starter_stats: dict,
    bullpen_stats: dict,
    park_factor: float,
    fg_pitching: dict,
    fg_batting: dict,
) -> float:
    """
    Proyección = runs_base × f_pitcheo × f_lineup × park_factor

    Cada factor está clampeado [0.60, 1.55].
    Piso absoluto: _PISO_CARRERAS (2.0).
    """
    runs_base = max(float(ofensiva.get('runs_last_5', 4.5) or 4.5), _PISO_CARRERAS)

    f_pit = _f_pitcheo(
        starter_stats.get('ERA', ERA_LIGA),
        bullpen_stats.get('ERA',  ERA_LIGA),
        fg_pitching.get('FIP', FIP_LIGA),
    )

    f_lin = _f_lineup(
        fg_batting.get('OPS', OPS_LIGA),
        fg_batting.get('wRC_plus_aprox', WRC_PLUS_LIGA),
    )

    proyeccion = runs_base * f_pit * f_lin * park_factor
    return round(max(proyeccion, _PISO_CARRERAS), 3)


def _nombre_a_venue(team_name: str) -> str:
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
    return MAPA.get(team_name, "default")


def proyectar_totales(partidos):
    pf_tabla = _get_park_factors()

    for partido in partidos:
        home_team = partido['home_team']
        away_team = partido['away_team']
        venue     = partido.get('venue') or _nombre_a_venue(home_team)

        pf_base     = pf_tabla.get(venue) or pf_tabla.get('default', 1.0)
        pf_ajustado = ajustar_park_factor(pf_base, partido.get('contexto', {}))

        home_bullpen = partido.get('home_bullpen', {'ERA': ERA_LIGA})
        away_bullpen = partido.get('away_bullpen', {'ERA': ERA_LIGA})

        # Stats avanzadas: pitching rival y batting propio
        fg_pitch_away = get_pitching(away_team)   # rival del home
        fg_pitch_home = get_pitching(home_team)   # rival del away
        fg_bat_home   = get_batting(home_team)
        fg_bat_away   = get_batting(away_team)

        home_proj = proyectar_carreras(
            partido['home_offense'], partido['away_stats'], away_bullpen,
            pf_ajustado, fg_pitching=fg_pitch_away, fg_batting=fg_bat_home,
        )
        away_proj = proyectar_carreras(
            partido['away_offense'], partido['home_stats'], home_bullpen,
            pf_ajustado, fg_pitching=fg_pitch_home, fg_batting=fg_bat_away,
        )

        partido.update({
            'proj_home':         home_proj,
            'proj_away':         away_proj,
            'proj_total':        round(home_proj + away_proj, 3),
            'park_factor_usado': pf_ajustado,
            'venue_usado':       venue,
            'era_rival_home':    _era_combinada(partido['away_stats']['ERA'], away_bullpen.get('ERA', ERA_LIGA)),
            'era_rival_away':    _era_combinada(partido['home_stats']['ERA'], home_bullpen.get('ERA', ERA_LIGA)),
            'fip_rival_home':    fg_pitch_away.get('FIP', FIP_LIGA),
            'fip_rival_away':    fg_pitch_home.get('FIP', FIP_LIGA),
            'wrc_home':          fg_bat_home.get('wRC_plus_aprox', WRC_PLUS_LIGA),
            'wrc_away':          fg_bat_away.get('wRC_plus_aprox', WRC_PLUS_LIGA),
        })

        print(
            f"[PROJ] {home_team} vs {away_team} | PF={pf_ajustado} "
            f"FIP_rival={fg_pitch_away.get('FIP','?')}/{fg_pitch_home.get('FIP','?')} "
            f"wRC+={fg_bat_home.get('wRC_plus_aprox','?')}/{fg_bat_away.get('wRC_plus_aprox','?')} | "
            f"Proy: {home_proj} - {away_proj} (total={partido['proj_total']})"
        )

    return partidos