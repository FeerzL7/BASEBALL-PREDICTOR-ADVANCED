# analysis/projections.py
from analysis.park_factors import calcular_park_factors

PESO_BULLPEN = 0.33
PESO_ABRIDOR = 1.0 - PESO_BULLPEN
ERA_LIGA     = 4.20
BARREL_LIGA  = 0.080

_PARK_FACTORS = None


def _get_park_factors() -> dict:
    global _PARK_FACTORS
    if _PARK_FACTORS is None:
        _PARK_FACTORS = calcular_park_factors()
    return _PARK_FACTORS


def ajustar_park_factor(base_pf: float, contexto: dict) -> float:
    if not contexto:
        return base_pf
    temperatura = contexto.get("clima", {}).get("temperatura", 22)
    viento      = contexto.get("clima", {}).get("viento_kph", 10)
    ajuste      = 1.0
    if temperatura >= 28: ajuste += 0.05
    elif temperatura <= 15: ajuste -= 0.05
    if viento >= 15: ajuste += 0.05
    if contexto.get("hora_local", 19) >= 20: ajuste -= 0.02
    return max(round(base_pf * ajuste, 3), 0.85)


def _era_combinada(starter_era: float, bullpen_era: float) -> float:
    return round(starter_era * PESO_ABRIDOR + bullpen_era * PESO_BULLPEN, 3)


def _xfip_combinado(starter_xfip: float, bullpen_era: float) -> float:
    return round(starter_xfip * PESO_ABRIDOR + bullpen_era * PESO_BULLPEN, 3)


def _factor_pitcheo(era: float, xfip: float) -> float:
    """
    ERA efectiva = 40% ERA observada + 60% xFIP.
    xFIP es más predictivo que ERA porque elimina el ruido de LOB% y HR/FB.
    Resultado normalizado por ERA de liga → clamp [0.50, 1.80].
    """
    era_efectiva = era * 0.40 + xfip * 0.60
    return max(0.50, min(era_efectiva / ERA_LIGA, 1.80))


def _factor_contacto(ofensiva: dict, starter_stats: dict) -> float:
    """
    Matchup de calidad de contacto: barrel% del lineup vs barrel% permitido
    por el lanzador, mezclado con hard-hit%.

    ratio > 1 → el lineup hace más contacto duro del que el pitcher suele permitir
    Escalado suave: factor = 1 + (ratio - 1) × 0.25 → rango [0.85, 1.20]
    """
    barrel_bat  = ofensiva.get('barrel_pct',  BARREL_LIGA)
    barrel_pit  = starter_stats.get('barrel_pct', BARREL_LIGA)
    hardhit_bat = ofensiva.get('hardhit_pct', 0.370)
    hardhit_pit = starter_stats.get('hardhit_pct', 0.370)

    ratio = (barrel_bat / max(barrel_pit, 0.01)) * 0.60 + \
            (hardhit_bat / max(hardhit_pit, 0.01)) * 0.40

    return round(max(0.85, min(1.0 + (ratio - 1.0) * 0.25, 1.20)), 4)


def proyectar_carreras(ofensiva, starter_stats, bullpen_stats, park_factor):
    era_comb  = _era_combinada(starter_stats['ERA'], bullpen_stats.get('ERA', ERA_LIGA))
    xfip_comb = _xfip_combinado(
        starter_stats.get('xFIP', starter_stats['ERA']),
        bullpen_stats.get('ERA', ERA_LIGA)
    )
    factor_pit      = _factor_pitcheo(era_comb, xfip_comb)
    factor_contacto = _factor_contacto(ofensiva, starter_stats)
    ops_ratio       = ofensiva['OPS'] / 0.730
    proyeccion      = (ofensiva['runs_last_5']
                       * factor_pit
                       * factor_contacto
                       * ops_ratio
                       * park_factor)
    return round(max(proyeccion, 1.5), 3)


def _nombre_a_venue(team_name: str) -> str:
    MAPA = {
        "Colorado Rockies": "Coors Field", "Boston Red Sox": "Fenway Park",
        "Texas Rangers": "Globe Life Field", "Oakland Athletics": "Oakland Coliseum",
        "Athletics": "Oakland Coliseum", "Los Angeles Dodgers": "Dodger Stadium",
        "San Diego Padres": "Petco Park", "New York Yankees": "Yankee Stadium",
        "Chicago Cubs": "Wrigley Field", "San Francisco Giants": "Oracle Park",
        "Houston Astros": "Minute Maid Park", "Minnesota Twins": "Target Field",
        "Seattle Mariners": "T-Mobile Park", "Miami Marlins": "loanDepot park",
        "Tampa Bay Rays": "Tropicana Field", "Baltimore Orioles": "Camden Yards",
        "Cleveland Guardians": "Progressive Field", "Detroit Tigers": "Comerica Park",
        "Chicago White Sox": "Guaranteed Rate Field", "Kansas City Royals": "Kauffman Stadium",
        "Los Angeles Angels": "Angel Stadium", "Arizona Diamondbacks": "Chase Field",
        "Atlanta Braves": "Truist Park", "Cincinnati Reds": "Great American Ball Park",
        "Milwaukee Brewers": "American Family Field", "Pittsburgh Pirates": "PNC Park",
        "St. Louis Cardinals": "Busch Stadium", "New York Mets": "Citi Field",
        "Philadelphia Phillies": "Citizens Bank Park", "Washington Nationals": "Nationals Park",
        "Toronto Blue Jays": "Rogers Centre",
    }
    return MAPA.get(team_name, "default")


def proyectar_totales(partidos):
    pf_tabla = _get_park_factors()

    for partido in partidos:
        home_team   = partido['home_team']
        venue       = partido.get('venue') or _nombre_a_venue(home_team)
        pf_base     = pf_tabla.get(venue) or pf_tabla.get('default', 1.0)
        pf_ajustado = ajustar_park_factor(pf_base, partido.get('contexto', {}))

        home_bullpen = partido.get('home_bullpen', {'ERA': ERA_LIGA, 'WHIP': 1.28})
        away_bullpen = partido.get('away_bullpen', {'ERA': ERA_LIGA, 'WHIP': 1.28})

        home_proj = proyectar_carreras(
            partido['home_offense'], partido['away_stats'], away_bullpen, pf_ajustado)
        away_proj = proyectar_carreras(
            partido['away_offense'], partido['home_stats'], home_bullpen, pf_ajustado)

        partido.update({
            'proj_home':         home_proj,
            'proj_away':         away_proj,
            'proj_total':        round(home_proj + away_proj, 3),
            'park_factor_usado': pf_ajustado,
            'venue_usado':       venue,
            'era_rival_home':    _era_combinada(partido['away_stats']['ERA'], away_bullpen['ERA']),
            'era_rival_away':    _era_combinada(partido['home_stats']['ERA'], home_bullpen['ERA']),
            'xfip_rival_home':   _xfip_combinado(
                partido['away_stats'].get('xFIP', partido['away_stats']['ERA']),
                away_bullpen['ERA']),
            'xfip_rival_away':   _xfip_combinado(
                partido['home_stats'].get('xFIP', partido['home_stats']['ERA']),
                home_bullpen['ERA']),
        })

        print(
            f"[PROJ] {home_team} vs {partido['away_team']} | "
            f"PF={pf_ajustado} venue={venue} | "
            f"xFIP rival home={partido['xfip_rival_home']} "
            f"away={partido['xfip_rival_away']} | "
            f"Proy: {home_proj} - {away_proj} (total={partido['proj_total']})"
        )

    return partidos