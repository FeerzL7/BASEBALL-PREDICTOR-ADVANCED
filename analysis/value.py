# analysis/value.py
#
# Lógica de decisión separada por mercado:
#
#   ML / RL  → lo que importa es la DIFERENCIA entre equipos
#              Variables clave: prob_home_win, prob_away_win (simulación Poisson),
#              ERA del abridor, racha reciente, H2H win rate
#              El pick es el equipo con mayor ventaja sobre la cuota
#
#   TOTAL    → lo que importa es la SUMA de carreras proyectadas
#              Variables clave: proj_total vs linea_total, park factor,
#              ERA combinada de ambos pitcheos, clima
#              El pick es Over/Under según la diferencia con la línea
#
# Cada mercado tiene sus propios umbrales de EV, probabilidad mínima
# y rango de cuota aceptable calibrados para su dinámica específica.

from scipy.stats import poisson

from utils.logger import get as get_log

log = get_log()

# ── Gestión de riesgo ─────────────────────────────────────────────────────────
KELLY_MAX_STAKE_PCT = 5.0
KELLY_FRACCION      = 0.5

UMBRAL_EV_ML       = 8      # subir de 5 → 8, filtrar picks débiles
UMBRAL_PROB_ML     = 0.48   # subir de 0.42 → 0.48, cerca del breakeven real
MIN_CUOTA_ML       = 1.70   # subir de 1.65 → 1.70
MAX_CUOTA_ML       = 2.30   # bajar de 2.50 → 2.30, cuotas muy altas son underdog puro

# ── Umbrales RL ───────────────────────────────────────────────────────────────
UMBRAL_EV_RL       = 15     # subir fuerte de 7 → 15
UMBRAL_PROB_RL     = 0.38   # subir de 0.33 → 0.38
MIN_CUOTA_RL       = 1.60   # subir de 1.55 → 1.60
MAX_CUOTA_RL       = 2.30   # bajar de 2.60 → 2.30

# ── Umbrales TOTAL ────────────────────────────────────────────────────────────
UMBRAL_EV_TOTAL    = 4      # mantener igual ← está funcionando
UMBRAL_PROB_TOTAL  = 0.52   # mantener igual
DIFF_LINEA_MIN     = 0.75   # mantener igual
MIN_CUOTA_TOTAL    = 1.75   # mantener igual
MAX_CUOTA_TOTAL    = 2.20   # mantener igual


# ── Utilidades comunes ────────────────────────────────────────────────────────

def _calc_ev(prob: float, cuota: float) -> float:
    return round((prob * cuota - 1) * 100, 2)


def _kelly(prob: float, cuota: float) -> float:
    """Kelly fraccionado con techo duro."""
    if not prob or not cuota or cuota <= 1:
        return 0.0
    b = cuota - 1
    kelly_full = (prob * (b + 1) - 1) / b
    if kelly_full <= 0:
        return 0.0
    return round(min(kelly_full * KELLY_FRACCION * 100, KELLY_MAX_STAKE_PCT), 2)


def _prob_ganar_poisson(mu_home: float, mu_away: float):
    """Probabilidad de victoria ML simulada con distribución Poisson."""
    prob_home = sum(
        poisson.pmf(h, mu_home) * poisson.pmf(a, mu_away)
        for h in range(15) for a in range(15) if h > a
    )
    return round(prob_home, 4), round(1 - prob_home, 4)  # type: ignore


# ── Decisión ML ──────────────────────────────────────────────────────────────

def _decidir_ml(partido: dict, prob_home: float, prob_away: float) -> dict:
    """Evalúa el mercado ML para un partido."""
    ho   = partido['home_team']
    aw   = partido['away_team']
    ml_h = partido.get('cuota_home')
    ml_a = partido.get('cuota_away')

    resultado = {
        'pick_ml':      'Sin datos',
        'valor_ml':     0.0,
        'kelly_ml':     0.0,
        'stake_pct_ml': 0.0,
        'prediccion_ml': None,
    }

    if not ml_h or not ml_a:
        return resultado

    ev_home = _calc_ev(prob_home, ml_h)
    ev_away = _calc_ev(prob_away, ml_a)

    if ev_home >= ev_away:
        pick, ev, prob, cuota = ho, ev_home, prob_home, ml_h
    else:
        pick, ev, prob, cuota = aw, ev_away, prob_away, ml_a

    stake = _kelly(prob, cuota)

    resultado.update({
        'pick_ml':      pick,
        'valor_ml':     ev,
        'kelly_ml':     stake,
        'stake_pct_ml': stake,
        'prediccion_ml': {
            'mercado': 'ML', 'seleccion': pick,
            'valor': ev, 'prob': prob,
            'cuota': cuota, 'stake_pct': stake,
        },
    })
    return resultado


# ── Decisión RL ───────────────────────────────────────────────────────────────

def _decidir_rl(partido: dict, prob_home: float, prob_away: float) -> dict:
    """
    Evalúa el mercado RL para un partido.

    FIX #2 — Usa rl_home_prob / rl_away_prob calculados por simulation.py
    (probabilidad real de cubrir +1.5 runlines via Poisson) en lugar de
    prob_home_win / prob_away_win (que son probabilidades de ganar ML y
    siempre son mayores, haciendo que más picks pasen el filtro de prob).

    Si los valores de RL de simulation.py no están disponibles en el partido
    (por compatibilidad con ejecuciones parciales), hace fallback a las
    probs ML como aproximación conservadora.
    """
    ho   = partido['home_team']
    aw   = partido['away_team']
    rl_h = partido.get('cuota_rl_home')
    rl_a = partido.get('cuota_rl_away')

    resultado = {
        'pick_rl':      'Sin datos',
        'valor_rl':     0.0,
        'kelly_rl':     0.0,
        'stake_pct_rl': 0.0,
        'prediccion_rl': None,
    }

    if not rl_h or not rl_a:
        return resultado

    # Probabilidades reales de cubrir el runline (simulación Poisson P[diff >= 2])
    # Calculadas en aplicar_simulaciones() → rl_home_prob, rl_away_prob
    rl_prob_home = partido.get('rl_home_prob', prob_home * 0.70)  # fallback conservador
    rl_prob_away = partido.get('rl_away_prob', prob_away * 0.70)  # fallback conservador

    # Elegir el equipo con mayor probabilidad de cubrir el RL
    if rl_prob_home >= rl_prob_away:
        pick, rl_cuota, rl_prob = ho, rl_h, rl_prob_home
    else:
        pick, rl_cuota, rl_prob = aw, rl_a, rl_prob_away

    ev    = _calc_ev(rl_prob, rl_cuota)
    stake = _kelly(rl_prob, rl_cuota)

    resultado.update({
        'pick_rl':      pick,
        'valor_rl':     ev,
        'kelly_rl':     stake,
        'stake_pct_rl': stake,
        'prediccion_rl': {
            'mercado': 'RL', 'seleccion': pick,
            'valor': ev, 'prob': rl_prob,
            'cuota': rl_cuota, 'stake_pct': stake,
        },
    })
    return resultado


# ── Decisión TOTAL ────────────────────────────────────────────────────────────

def _prob_total_poisson(mu_total: float, linea: float, pick: str) -> float:
    """
    Probabilidad exacta de Over/Under usando suma de Poisson.
    Over: P(X > linea)   donde X ~ Poisson(mu_total)
    Under: P(X < linea)  excluye push (X == linea)
    """
    mu = max(mu_total, 0.1)
    if pick == 'Over':
        return float(poisson.sf(linea, mu))
    else:
        return float(poisson.cdf(linea - 1, mu))


def _decidir_total(partido: dict) -> dict:
    """
    Evalúa el mercado de totales para un partido.

    Lógica específica de totales:
      1. Usa proj_total (suma de proyecciones de ambos equipos) vs linea_total
      2. Solo apuesta si la diferencia supera DIFF_LINEA_MIN
      3. Calcula probabilidad Poisson de la suma total de carreras
      4. Aplica umbrales distintos a ML: UMBRAL_PROB_TOTAL y rango de cuota propio
      5. Usa park_factor_usado para ajustar confianza:
         un PF extremo (>1.20 o <0.90) con proyección en la dirección correcta
         añade confianza; en dirección contraria la reduce
    """
    ou_line    = partido.get('linea_total')
    ou_over    = partido.get('cuota_over')
    ou_under   = partido.get('cuota_under')
    proj_total = partido.get('proj_total', 0)
    pf         = partido.get('park_factor_usado', 1.0) or 1.0

    resultado = {
        'pick_total':      'Sin ventaja clara',
        'valor_total':     0.0,
        'stake_pct_total': 0.0,
        'prediccion_total': None,
    }

    if not ou_line or not ou_over or not ou_under or proj_total <= 0:
        return resultado

    diff = proj_total - ou_line

    # Diferencia insuficiente → sin ventaja
    if abs(diff) < DIFF_LINEA_MIN:
        return resultado

    pick_t  = 'Over' if diff > 0 else 'Under'
    cuota_t = ou_over if pick_t == 'Over' else ou_under

    # Probabilidad Poisson del total proyectado
    prob_t  = _prob_total_poisson(proj_total, ou_line, pick_t)

    # Ajuste de probabilidad por park factor
    if pick_t == 'Over':
        if pf > 1.10:
            prob_t = min(prob_t * 1.03, 0.85)
        elif pf < 0.90:
            prob_t = prob_t * 0.97
    else:  # Under
        if pf < 0.90:
            prob_t = min(prob_t * 1.03, 0.85)
        elif pf > 1.10:
            prob_t = prob_t * 0.97

    ev_t    = _calc_ev(prob_t, cuota_t)
    stake_t = 0.0

    # Stake solo si cumple TODOS los criterios de totales
    cuota_ok = MIN_CUOTA_TOTAL <= cuota_t <= MAX_CUOTA_TOTAL
    if (prob_t  >= UMBRAL_PROB_TOTAL and
            ev_t >= UMBRAL_EV_TOTAL and
            cuota_ok):
        stake_t = _kelly(prob_t, cuota_t)

    resultado.update({
        'pick_total':      pick_t,
        'valor_total':     ev_t,
        'stake_pct_total': stake_t,
        'prediccion_total': {
            'mercado': 'TOTAL', 'seleccion': pick_t,
            'valor': ev_t, 'prob': round(prob_t, 3),
            'cuota': cuota_t, 'stake_pct': stake_t,
        },
    })
    return resultado


# ── Selección del mejor pick ──────────────────────────────────────────────────

def _mejor_pick(partido: dict, ml: dict, rl: dict, total: dict) -> str:
    """
    Compara los tres mercados y devuelve el identificador del mejor pick.

    Criterios por mercado (todos deben cumplirse):
      ML:    EV >= UMBRAL_EV_ML, prob ML >= UMBRAL_PROB_ML, cuota en rango
      RL:    EV >= UMBRAL_EV_RL, prob RL >= UMBRAL_PROB_RL, cuota en rango
      TOTAL: EV >= UMBRAL_EV_TOTAL, prob >= UMBRAL_PROB_TOTAL,
             cuota en rango, stake > 0 (garantiza que pasó todos los filtros)

    Si más de uno cumple, gana el de mayor EV.
    """
    candidatos = []

    # ML
    ev_ml    = ml.get('valor_ml', 0)
    prob_ml  = (partido.get('prob_home_win', 0)
                if ml.get('pick_ml') == partido['home_team']
                else partido.get('prob_away_win', 0))
    cuota_ml = (partido.get('cuota_home')
                if ml.get('pick_ml') == partido['home_team']
                else partido.get('cuota_away')) or 0

    if (ev_ml   >= UMBRAL_EV_ML and
            prob_ml >= UMBRAL_PROB_ML and
            MIN_CUOTA_ML <= cuota_ml <= MAX_CUOTA_ML):
        candidatos.append(('ML', ev_ml, f"ML: {ml['pick_ml']}"))

    # RL — FIX #2: usa prob de cubrir RL (rl_home_prob/rl_away_prob),
    # no la probabilidad de ganar el moneyline
    ev_rl    = rl.get('valor_rl', 0)
    prob_rl  = (partido.get('rl_home_prob', 0)
                if rl.get('pick_rl') == partido['home_team']
                else partido.get('rl_away_prob', 0))
    cuota_rl = (partido.get('cuota_rl_home')
                if rl.get('pick_rl') == partido['home_team']
                else partido.get('cuota_rl_away')) or 0

    if (ev_rl   >= UMBRAL_EV_RL and
            prob_rl >= UMBRAL_PROB_RL and
            MIN_CUOTA_RL <= cuota_rl <= MAX_CUOTA_RL):
        candidatos.append(('RL', ev_rl, f"RL: {rl['pick_rl']}"))

    # TOTAL — solo entra si stake > 0 (pasó todos los filtros internos)
    ev_total    = total.get('valor_total', 0)
    stake_total = total.get('stake_pct_total', 0)

    if stake_total > 0 and ev_total >= UMBRAL_EV_TOTAL:
        candidatos.append(('TOTAL', ev_total, f"TOTAL: {total['pick_total']}"))

    if not candidatos:
        return 'Ninguno'

    # Gana el de mayor EV
    mejor = max(candidatos, key=lambda x: x[1])
    return mejor[2]


# ── Punto de entrada principal ────────────────────────────────────────────────

def analizar_valor(partidos: list) -> list:
    for partido in partidos:
        ho = partido['home_team']
        aw = partido['away_team']

        # Proyecciones del pipeline completo (ya calculadas en proyectar_totales)
        proj_home  = partido.get('proj_home', 4.5)
        proj_away  = partido.get('proj_away', 4.5)

        # Probabilidades Poisson de victoria ML
        prob_home, prob_away = _prob_ganar_poisson(proj_home, proj_away)

        partido['prob_home_win'] = prob_home
        partido['prob_away_win'] = prob_away

        # ── Evaluar cada mercado de forma independiente ────────────────────────
        ml    = _decidir_ml(partido, prob_home, prob_away)
        rl    = _decidir_rl(partido, prob_home, prob_away)
        total = _decidir_total(partido)

        # ── Consolidar resultados en el partido ────────────────────────────────
        partido.update({
            # ML
            'pick_ml':      ml['pick_ml'],
            'valor_ml':     ml['valor_ml'],
            'kelly_ml':     ml['kelly_ml'],
            'stake_pct_ml': ml['stake_pct_ml'],
            # RL
            'pick_rl':      rl['pick_rl'],
            'valor_rl':     rl['valor_rl'],
            'kelly_rl':     rl['kelly_rl'],
            'stake_pct_rl': rl['stake_pct_rl'],
            # Total
            'pick_total':      total['pick_total'],
            'valor_total':     total['valor_total'],
            'stake_pct_total': total['stake_pct_total'],
            # Proyecciones (asegurar que están en el dict)
            'proj_home':    proj_home,
            'proj_away':    proj_away,
            'linea_total':  partido.get('linea_total'),
            'cuota_over':   partido.get('cuota_over'),
            'cuota_under':  partido.get('cuota_under'),
        })

        # Predicciones para trazabilidad
        predicciones = [v for v in [
            ml.get('prediccion_ml'),
            rl.get('prediccion_rl'),
            total.get('prediccion_total'),
        ] if v is not None]
        partido['predicciones'] = predicciones

        # Seleccionar mejor pick
        partido['mejor_pick'] = _mejor_pick(partido, ml, rl, total)

        log.debug(
            f"{ho} vs {aw} | "
            f"Proy: {proj_home:.2f}-{proj_away:.2f} | "
            f"ML: {ml['pick_ml']} EV={ml['valor_ml']:.1f} "
            f"stake={ml['stake_pct_ml']}% | "
            f"RL: {rl['pick_rl']} EV={rl['valor_rl']:.1f} "
            f"stake={rl['stake_pct_rl']}% | "
            f"Total: {total['pick_total']} EV={total['valor_total']:.1f} "
            f"stake={total['stake_pct_total']}% | "
            f"Mejor: {partido['mejor_pick']}"
        )

    return partidos