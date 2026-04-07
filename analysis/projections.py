# analysis/projections.py
from analysis.park_factors import calcular_park_factors
from analysis.statcast import (
    get_pitching, get_batting,
    ERA_LIGA, FIP_LIGA, WRC_PLUS_LIGA, OPS_LIGA,
)
from utils.logger import get as get_log

log = get_log()

PESO_BULLPEN   = 0.33
PESO_ABRIDOR   = 1.0 - PESO_BULLPEN
_F_MIN         = 0.60
_F_MAX         = 1.55
_PARK_FACTORS  = None
_PISO_CARRERAS = 2.0

# Mínimo de partidos H2H para incluir ese factor
H2H_MIN_PARTIDOS = 3
PESO_RECIENTE    = 0.80
PESO_H2H         = 0.20


# ── Clasificación de estadios ─────────────────────────────────────────────────
#
# CERRADO      → temperatura interior controlada (~21°C siempre)
#                El clima exterior no afecta el juego.
#
# RETRACTIL    → techo que se abre o cierra según el clima.
#                Si temperatura exterior < TEMP_RETRACTIL_UMBRAL,
#                asumimos techo cerrado → aplicar temperatura interior fija.
#                Si temperatura >= umbral, asumimos abierto → clima real.
#
# ABIERTO      → sin techo, clima exterior directo (todos los demás).
#
# Fuente: MLB official ballpark guide 2025.

ESTADIOS_CERRADOS = {
    'Tropicana Field',          # Tampa Bay Rays    — cúpula fija
    'Rogers Centre',            # Toronto Blue Jays — techo retráctil, default cerrado
    'loanDepot park',           # Miami Marlins     — techo retráctil, default cerrado
}

# FIX #3 — Oracle Park eliminado de ESTADIOS_RETRACTILES.
# Oracle Park (San Francisco Giants) es un estadio ABIERTO sin techo.
# Clasificarlo como retráctil causaba que con temp < 12°C el sistema
# usara temperatura interior (21°C) en lugar de la real (~8-10°C en abril),
# inflando las proyecciones de carreras para partidos en Oracle Park.
ESTADIOS_RETRACTILES = {
    'Chase Field',              # Arizona Diamondbacks
    'American Family Field',    # Milwaukee Brewers
    'Globe Life Field',         # Texas Rangers
    'T-Mobile Park',            # Seattle Mariners
    'Minute Maid Park',         # Houston Astros
}

# Si la temperatura exterior está por debajo de este umbral y el estadio
# tiene techo retráctil, asumimos que el techo está cerrado ese día.
TEMP_RETRACTIL_UMBRAL = 12.0   # °C

# Temperatura interior fija de estadios cerrados/bajo techo
TEMP_INTERIOR         = 21.0   # °C

# Ajuste por viento en estadios abiertos (km/h)
VIENTO_UMBRAL_ALTO    = 20.0
VIENTO_UMBRAL_MEDIO   = 12.0


# ── Tabla de ajuste por temperatura ──────────────────────────────────────────
#
# Basado en análisis estadístico de runs/game por temperatura en MLB:
# - Temperatura alta → más carreras (aire menos denso, menor resistencia a la pelota,
#   más fatiga del pitcheo, más actividad muscular del bateador)
# - Temperatura baja → menos carreras (efecto inverso + pelotas más pesadas)
#
# Cada entrada: (temp_min, temp_max_exclusivo, ajuste_multiplicativo)
# El ajuste se aplica SOBRE el park factor base.

_AJUSTE_TEMP = [
    (32,  float('inf'), +0.09),   # > 32°C  → +9%
    (28,  32,           +0.05),   # 28-32°C → +5%
    (24,  28,           +0.02),   # 24-28°C → +2%
    (18,  24,            0.00),   # 18-24°C → neutro
    (13,  18,           -0.03),   # 13-18°C → -3%
    (8,   13,           -0.06),   # 8-13°C  → -6%
    (-99,  8,           -0.09),   # < 8°C   → -9%
]


def _ajuste_por_temperatura(temp: float) -> float:
    """Devuelve el factor multiplicativo de ajuste por temperatura."""
    for t_min, t_max, ajuste in _AJUSTE_TEMP:
        if t_min <= temp < t_max:
            return ajuste
    return 0.0


def _temperatura_efectiva(venue: str, temp_exterior: float) -> tuple[float, str]:
    """
    Devuelve (temperatura_efectiva, tipo_estadio) según el tipo de recinto.

    Para estadios cerrados: temperatura interior fija.
    Para estadios retráctiles: temperatura interior si hace frío, exterior si no.
    Para estadios abiertos: temperatura exterior directa.
    """
    if venue in ESTADIOS_CERRADOS:
        return TEMP_INTERIOR, 'cerrado'

    if venue in ESTADIOS_RETRACTILES:
        if temp_exterior < TEMP_RETRACTIL_UMBRAL:
            return TEMP_INTERIOR, 'retractil_cerrado'
        return temp_exterior, 'retractil_abierto'

    return temp_exterior, 'abierto'


def _ajuste_viento(venue: str, tipo: str, viento_kph: float,
                   hora: int) -> float:
    """
    Ajuste adicional por viento, solo en estadios abiertos o retráctiles abiertos.
    Viento fuerte favorece bateo de largo (HR) y penaliza pitcheo de control.
    """
    if tipo in ('cerrado', 'retractil_cerrado'):
        return 0.0   # sin efecto de viento bajo techo

    if viento_kph >= VIENTO_UMBRAL_ALTO:
        return +0.04
    if viento_kph >= VIENTO_UMBRAL_MEDIO:
        return +0.02
    return 0.0


def _ajuste_nocturno(hora: int) -> float:
    """Juegos nocturnos tienen ligeramente menos carreras por menor visibilidad."""
    return -0.02 if hora >= 20 else 0.0


# ── Park factor ajustado ──────────────────────────────────────────────────────

def ajustar_park_factor(base_pf: float, contexto: dict,
                        venue: str = 'default') -> tuple[float, dict]:
    """
    Calcula el park factor final combinando:
      1. Park factor base (histórico del estadio)
      2. Ajuste por temperatura efectiva (según tipo de estadio)
      3. Ajuste por viento
      4. Ajuste nocturno

    Devuelve (pf_final, detalle_ajustes) para trazabilidad en logs.
    """
    if not contexto:
        return max(round(base_pf, 3), 0.85), {}

    temp_ext  = float(contexto.get("clima", {}).get("temperatura", 20))
    viento    = float(contexto.get("clima", {}).get("viento_kph",  10))
    hora      = int(contexto.get("hora_local", 19))

    temp_ef, tipo = _temperatura_efectiva(venue, temp_ext)

    adj_temp   = _ajuste_por_temperatura(temp_ef)
    adj_viento = _ajuste_viento(venue, tipo, viento, hora)
    adj_noche  = _ajuste_nocturno(hora)

    ajuste_total = adj_temp + adj_viento + adj_noche
    pf_final     = max(round(base_pf * (1 + ajuste_total), 3), 0.85)
    pf_final     = min(pf_final, 1.60)   # techo: evitar valores extremos

    detalle = {
        'tipo_estadio':  tipo,
        'temp_exterior': temp_ext,
        'temp_efectiva': temp_ef,
        'adj_temp':      round(adj_temp,   3),
        'adj_viento':    round(adj_viento, 3),
        'adj_noche':     round(adj_noche,  3),
        'ajuste_total':  round(ajuste_total, 3),
    }

    return pf_final, detalle


# ── Resto de funciones del modelo (sin cambios) ───────────────────────────────

def _get_park_factors() -> dict:
    global _PARK_FACTORS
    if _PARK_FACTORS is None:
        _PARK_FACTORS = calcular_park_factors()
    return _PARK_FACTORS


def _era_combinada(starter_era: float, bullpen_era: float) -> float:
    starter_era = max(1.0, min(float(starter_era or ERA_LIGA), 9.0))
    bullpen_era = max(1.0, min(float(bullpen_era or ERA_LIGA), 9.0))
    return round(starter_era * PESO_ABRIDOR + bullpen_era * PESO_BULLPEN, 3)


def _clamp(v: float) -> float:
    return max(_F_MIN, min(v, _F_MAX))


def _f_pitcheo(starter_era: float, bullpen_era: float, fip: float) -> float:
    era_comb = _era_combinada(starter_era, bullpen_era)
    fip      = max(2.0, min(fip, 7.0))
    return _clamp(era_comb / ERA_LIGA * 0.55 + fip / FIP_LIGA * 0.45)


def _f_lineup(ops: float, wrc_aprox: float) -> float:
    ops       = max(0.50, min(ops,       1.10))
    wrc_aprox = max(50.0, min(wrc_aprox, 170.0))
    return _clamp((ops / OPS_LIGA + wrc_aprox / WRC_PLUS_LIGA) / 2.0)


def _base_carreras(runs_last_5: float, h2h_prom: float | None,
                   n_partidos_h2h: int) -> float:
    base = max(float(runs_last_5 or 4.5), _PISO_CARRERAS)
    if h2h_prom is None or n_partidos_h2h < H2H_MIN_PARTIDOS:
        return base
    h2h_val = max(float(h2h_prom), _PISO_CARRERAS)
    return round(max(base * PESO_RECIENTE + h2h_val * PESO_H2H, _PISO_CARRERAS), 3)


def proyectar_carreras(
    ofensiva:       dict,
    starter_stats:  dict,
    bullpen_stats:  dict,
    park_factor:    float,
    fg_pitching:    dict,
    fg_batting:     dict,
    h2h_prom:       float | None = None,
    n_partidos_h2h: int = 0,
) -> float:
    base  = _base_carreras(ofensiva.get('runs_last_5', 4.5), h2h_prom, n_partidos_h2h)
    f_pit = _f_pitcheo(
        starter_stats.get('ERA_efectiva', starter_stats['ERA']),
        bullpen_stats.get('ERA', ERA_LIGA),
        fg_pitching.get('FIP', FIP_LIGA),
    )
    f_lin = _f_lineup(
        fg_batting.get('OPS',            OPS_LIGA),
        fg_batting.get('wRC_plus_aprox', WRC_PLUS_LIGA),
    )
    return round(max(base * f_pit * f_lin * park_factor, _PISO_CARRERAS), 3)


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


# ── Punto de entrada principal ────────────────────────────────────────────────

def proyectar_totales(partidos: list) -> list:
    pf_tabla = _get_park_factors()

    for partido in partidos:
        home_team = partido['home_team']
        away_team = partido['away_team']

        # Venue: preferir el que viene del schedule (venue_name),
        # con fallback al mapa equipo→venue
        venue = (partido.get('venue_name')
                 or partido.get('venue')
                 or _nombre_a_venue(home_team))

        pf_base     = pf_tabla.get(venue) or pf_tabla.get('default', 1.0)
        contexto    = partido.get('contexto', {})

        # Park factor con ajuste por temperatura y tipo de estadio.
        # REQUIERE que analizar_contexto() haya corrido ANTES en main.py.
        pf_ajustado, detalle_pf = ajustar_park_factor(pf_base, contexto, venue)

        home_bullpen  = partido.get('home_bullpen', {'ERA': ERA_LIGA})
        away_bullpen  = partido.get('away_bullpen', {'ERA': ERA_LIGA})
        fg_pitch_away = get_pitching(away_team)
        fg_pitch_home = get_pitching(home_team)
        fg_bat_home   = get_batting(home_team)
        fg_bat_away   = get_batting(away_team)

        h2h           = partido.get('h2h', {})
        n_h2h         = int(h2h.get('partidos', 0) or 0)
        h2h_home_prom = h2h.get('runs_home_prom')
        h2h_away_prom = h2h.get('runs_away_prom')

        home_proj = proyectar_carreras(
            partido['home_offense'], partido['away_stats'], away_bullpen,
            pf_ajustado, fg_pitch_away, fg_bat_home,
            h2h_prom=h2h_home_prom, n_partidos_h2h=n_h2h,
        )
        away_proj = proyectar_carreras(
            partido['away_offense'], partido['home_stats'], home_bullpen,
            pf_ajustado, fg_pitch_home, fg_bat_away,
            h2h_prom=h2h_away_prom, n_partidos_h2h=n_h2h,
        )

        partido.update({
            'proj_home':         home_proj,
            'proj_away':         away_proj,
            'proj_total':        round(home_proj + away_proj, 3),
            'park_factor_usado': pf_ajustado,
            'park_factor_base':  pf_base,
            'venue_usado':       venue,
            'tipo_estadio':      detalle_pf.get('tipo_estadio', 'abierto'),
            'temp_efectiva':     detalle_pf.get('temp_efectiva', 20.0),
            'ajuste_temp':       detalle_pf.get('adj_temp', 0.0),
            'era_rival_home':    _era_combinada(
                partido['away_stats'].get('ERA_efectiva', partido['away_stats']['ERA']),
                away_bullpen.get('ERA', ERA_LIGA),
            ),
            'era_rival_away':    _era_combinada(
                partido['home_stats'].get('ERA_efectiva', partido['home_stats']['ERA']),
                home_bullpen.get('ERA', ERA_LIGA),
            ),
            'fip_rival_home':    fg_pitch_away.get('FIP', FIP_LIGA),
            'fip_rival_away':    fg_pitch_home.get('FIP', FIP_LIGA),
            'wrc_home':          fg_bat_home.get('wRC_plus_aprox', WRC_PLUS_LIGA),
            'wrc_away':          fg_bat_away.get('wRC_plus_aprox', WRC_PLUS_LIGA),
            'h2h_partidos':      n_h2h,
        })

        tipo  = detalle_pf.get('tipo_estadio', 'abierto')
        t_ext = detalle_pf.get('temp_exterior', 20)
        t_ef  = detalle_pf.get('temp_efectiva', 20)
        adj   = detalle_pf.get('ajuste_total',  0)

        log.debug(
            f"{home_team} vs {away_team} | "
            f"venue={venue} tipo={tipo} "
            f"T_ext={t_ext}°C T_ef={t_ef}°C adj={adj:+.0%} "
            f"PF_base={pf_base} PF_final={pf_ajustado} | "
            f"ERA_ef={partido['away_stats'].get('ERA_efectiva','?')}/"
            f"{partido['home_stats'].get('ERA_efectiva','?')} "
            f"FIP={fg_pitch_away.get('FIP','?')}/{fg_pitch_home.get('FIP','?')} | "
            f"Proy: {home_proj} - {away_proj} (total={partido['proj_total']})"
        )

    return partidos