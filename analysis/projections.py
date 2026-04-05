# analysis/projections.py
from analysis.park_factors import calcular_park_factors
from analysis.statcast import (
    get_pitching, get_batting,
    ERA_LIGA, FIP_LIGA, WRC_PLUS_LIGA, OPS_LIGA,
)
from utils.logger import get as get_log

log = get_log()

PESO_BULLPEN = 0.33
PESO_ABRIDOR = 1.0 - PESO_BULLPEN

# Pesos de la base de carreras:
#   runs_last_5  → producción reciente del lineup (más reactiva)
#   h2h_prom     → historial entre estos dos equipos específicos
# El H2H solo entra si hay suficientes partidos (H2H_MIN_PARTIDOS).
# Con pocos partidos, el promedio es ruidoso y es mejor ignorarlo.
PESO_RECIENTE  = 0.80
PESO_H2H       = 0.20
H2H_MIN_PARTIDOS = 3   # mínimo de partidos H2H para considerarlo confiable

# Clamps de factores multiplicativos
_F_MIN = 0.60
_F_MAX = 1.55

_PARK_FACTORS  = None
_PISO_CARRERAS = 2.0


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
    era_comb = _era_combinada(starter_era, bullpen_era)
    fip      = max(2.0, min(fip, 7.0))
    f_era    = era_comb / ERA_LIGA
    f_fip    = fip / FIP_LIGA
    return _clamp(f_era * 0.55 + f_fip * 0.45)


def _f_lineup(ops: float, wrc_aprox: float) -> float:
    ops       = max(0.50, min(ops,       1.10))
    wrc_aprox = max(50.0, min(wrc_aprox, 170.0))
    f_ops = ops       / OPS_LIGA
    f_wrc = wrc_aprox / WRC_PLUS_LIGA
    return _clamp((f_ops + f_wrc) / 2.0)


def _base_carreras(runs_last_5: float, h2h_prom: float | None,
                   n_partidos_h2h: int) -> float:
    """
    Combina la producción reciente del lineup con el historial H2H.

    Lógica:
      - Si hay suficientes partidos H2H (>= H2H_MIN_PARTIDOS), mezcla
        runs_last_5 (80%) con h2h_prom (20%).
      - Si el H2H es insuficiente o no existe, usa solo runs_last_5.

    Por qué 80/20 y no más peso al H2H:
      El H2H captura dinámicas reales (un equipo que históricamente
      golpea bien al pitcheo rival), pero con muestras pequeñas de
      temporada (~5-10 partidos) tiene alta varianza. El 20% es
      suficiente para que el dato mueva la proyección ~0.3-0.5 carreras
      sin arriesgar que un outlier distorsione todo.
    """
    base = max(float(runs_last_5 or 4.5), _PISO_CARRERAS)

    if h2h_prom is None or n_partidos_h2h < H2H_MIN_PARTIDOS:
        return base

    h2h_val = max(float(h2h_prom), _PISO_CARRERAS)
    combinado = base * PESO_RECIENTE + h2h_val * PESO_H2H
    return round(max(combinado, _PISO_CARRERAS), 3)


def proyectar_carreras(
    ofensiva:      dict,
    starter_stats: dict,
    bullpen_stats: dict,
    park_factor:   float,
    fg_pitching:   dict,
    fg_batting:    dict,
    h2h_prom:      float | None = None,
    n_partidos_h2h: int = 0,
) -> float:
    """
    Proyección de carreras con cuatro factores:

      base × f_pitcheo × f_lineup × park_factor

    donde base = combinación de runs_last_5 y h2h_prom.
    """
    base = _base_carreras(
        ofensiva.get('runs_last_5', 4.5),
        h2h_prom,
        n_partidos_h2h,
    )

    f_pit = _f_pitcheo(
        starter_stats.get('ERA_efectiva', starter_stats['ERA']),
        bullpen_stats.get('ERA', ERA_LIGA),
        fg_pitching.get('FIP', FIP_LIGA),
    )

    f_lin = _f_lineup(
        fg_batting.get('OPS',            OPS_LIGA),
        fg_batting.get('wRC_plus_aprox', WRC_PLUS_LIGA),
    )

    proyeccion = base * f_pit * f_lin * park_factor
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


def proyectar_totales(partidos: list) -> list:
    pf_tabla = _get_park_factors()

    for partido in partidos:
        home_team = partido['home_team']
        away_team = partido['away_team']
        venue     = partido.get('venue') or _nombre_a_venue(home_team)

        pf_base     = pf_tabla.get(venue) or pf_tabla.get('default', 1.0)
        pf_ajustado = ajustar_park_factor(pf_base, partido.get('contexto', {}))

        home_bullpen = partido.get('home_bullpen', {'ERA': ERA_LIGA})
        away_bullpen = partido.get('away_bullpen', {'ERA': ERA_LIGA})

        # Stats avanzadas Fangraphs/statsapi
        fg_pitch_away = get_pitching(away_team)
        fg_pitch_home = get_pitching(home_team)
        fg_bat_home   = get_batting(home_team)
        fg_bat_away   = get_batting(away_team)

        # Datos H2H — extraer del partido si h2h.py ya los calculó
        h2h           = partido.get('h2h', {})
        n_h2h         = int(h2h.get('partidos', 0) or 0)
        h2h_home_prom = h2h.get('runs_home_prom')   # carreras home en H2H
        h2h_away_prom = h2h.get('runs_away_prom')   # carreras away en H2H

        # Trazabilidad en log
        h2h_str = (f"H2H={n_h2h}p home={h2h_home_prom}/away={h2h_away_prom}"
                   if n_h2h >= H2H_MIN_PARTIDOS else "H2H insuf.")

        home_proj = proyectar_carreras(
            partido['home_offense'],
            partido['away_stats'],
            away_bullpen,
            pf_ajustado,
            fg_pitching=fg_pitch_away,
            fg_batting=fg_bat_home,
            h2h_prom=h2h_home_prom,
            n_partidos_h2h=n_h2h,
        )
        away_proj = proyectar_carreras(
            partido['away_offense'],
            partido['home_stats'],
            home_bullpen,
            pf_ajustado,
            fg_pitching=fg_pitch_home,
            fg_batting=fg_bat_away,
            h2h_prom=h2h_away_prom,
            n_partidos_h2h=n_h2h,
        )

        partido.update({
            'proj_home':         home_proj,
            'proj_away':         away_proj,
            'proj_total':        round(home_proj + away_proj, 3),
            'park_factor_usado': pf_ajustado,
            'venue_usado':       venue,
            'era_rival_home':    _era_combinada(
                partido['away_stats'].get('ERA_efectiva', partido['away_stats']['ERA']),
                away_bullpen.get('ERA', ERA_LIGA)
            ),
            'era_rival_away':    _era_combinada(
                partido['home_stats'].get('ERA_efectiva', partido['home_stats']['ERA']),
                home_bullpen.get('ERA', ERA_LIGA)
            ),
            'fip_rival_home':    fg_pitch_away.get('FIP', FIP_LIGA),
            'fip_rival_away':    fg_pitch_home.get('FIP', FIP_LIGA),
            'wrc_home':          fg_bat_home.get('wRC_plus_aprox', WRC_PLUS_LIGA),
            'wrc_away':          fg_bat_away.get('wRC_plus_aprox', WRC_PLUS_LIGA),
            'h2h_partidos':      n_h2h,
        })

        log.debug(
            f"{home_team} vs {away_team} | PF={pf_ajustado} "
            f"ERA_ef={partido['away_stats'].get('ERA_efectiva','?')}/"
            f"{partido['home_stats'].get('ERA_efectiva','?')} "
            f"FIP={fg_pitch_away.get('FIP','?')}/{fg_pitch_home.get('FIP','?')} "
            f"wRC+={fg_bat_home.get('wRC_plus_aprox','?')}/"
            f"{fg_bat_away.get('wRC_plus_aprox','?')} "
            f"{h2h_str} | "
            f"Proy: {home_proj} - {away_proj} (total={partido['proj_total']})"
        )

    return partidos