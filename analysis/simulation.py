from utils.logger import get as get_log
from utils import poisson_math as poisson

log = get_log()


def simular_probabilidades(home, away, max_runs=15):
    prob_home_win = 0.0
    prob_away_win = 0.0
    for h in range(max_runs):
        for a in range(max_runs):
            p = poisson.pmf(h, home) * poisson.pmf(a, away)
            if h > a:
                prob_home_win += p
            elif a > h:
                prob_away_win += p
    total_decidido = prob_home_win + prob_away_win
    if total_decidido <= 0:
        return 0.5, 0.5
    return round(prob_home_win / total_decidido, 4), round(prob_away_win / total_decidido, 4)


def simular_runline(team_proj, opp_proj, point=-1.5, max_runs=15):
    cover_prob = 0.0
    for t in range(max_runs):
        for o in range(max_runs):
            p = poisson.pmf(t, team_proj) * poisson.pmf(o, opp_proj)
            if t + point > o:
                cover_prob += p
    return round(cover_prob, 4)


def calcular_valor(prob, cuota):
    return round((prob * cuota - 1) * 100, 2)


def calcular_kelly(probabilidad: float, cuota: float) -> float:
    if probabilidad is None or cuota is None:
        return 0.0
    b = cuota - 1
    if b <= 0:
        return 0.0
    kelly = (probabilidad * (b + 1) - 1) / b
    return round(kelly * 100, 2) if kelly > 0 else 0.0


def aplicar_simulaciones(partidos: list) -> list:
    """
    Aplica simulaciones Poisson usando las proyecciones del pipeline.

    Orden interno:
      1. Ensemble (Poisson + Regresión Lineal) ajusta proj_home/proj_away
         si hay datos de carreras recientes disponibles.
      2. Simulación Poisson estándar sobre las proyecciones (ya ajustadas).
      3. Simulación de runline sobre las mismas proyecciones.

    El ensemble es transparente para todo el downstream: value.py, markets.py,
    etc. siguen consumiendo proj_home/proj_away sin saber si fueron ajustados.
    """
    # ── Paso 1: Ensemble Poisson + Regresión Lineal ───────────────────────────
    # Importación lazy para evitar dependencia circular si ensemble.py
    # necesita algún módulo que importa simulation.py en el futuro.
    try:
        from analysis.ensemble import ajustar_proyecciones_ensemble
        partidos = ajustar_proyecciones_ensemble(partidos)
    except Exception as e:
        # Fallback silencioso: si el ensemble falla por cualquier razón,
        # las proyecciones Poisson originales se mantienen intactas.
        log.debug(f"Ensemble desactivado (fallback a Poisson puro): {e}")

    # ── Paso 2: Simulación de probabilidades ──────────────────────────────────
    for p in partidos:
        home = max(p.get('proj_home', 4.5), 0.5)
        away = max(p.get('proj_away', 4.5), 0.5)

        prob_home, prob_away = simular_probabilidades(home, away)
        p['prob_home_win'] = prob_home
        p['prob_away_win'] = prob_away

        p['rl_home_prob'] = simular_runline(home, away, p.get('linea_rl_home') or -1.5)
        p['rl_away_prob'] = simular_runline(away, home, p.get('linea_rl_away') or -1.5)

    return partidos
