# analysis/value.py

# ── Gestión de riesgo ─────────────────────────────────────────────────────────
KELLY_MAX_STAKE_PCT = 5.0   # techo absoluto: nunca más del 5% del bankroll
KELLY_FRACCION      = 0.5   # Kelly fraccionado conservador

# ── Umbrales de valor esperado por mercado ────────────────────────────────────
UMBRAL_VALOR_ML    = 5
UMBRAL_VALOR_RL    = 7
UMBRAL_VALOR_TOTAL = 4

# ── Filtros de calidad ────────────────────────────────────────────────────────
UMBRAL_PROB_MIN    = 0.40
MIN_CUOTA_ACEPTADA = 1.65
MAX_CUOTA_ACEPTADA = 2.50

# Probabilidad mínima para apostar totales (Over o Under)
# Más conservador que ML porque la muestra Poisson es menos precisa en colas
UMBRAL_PROB_TOTAL  = 0.52


def analizar_valor(partidos):
    from scipy.stats import poisson

    def simular_prob_ganar(mu_home, mu_away):
        prob_home = sum(
            poisson.pmf(h, mu_home) * poisson.pmf(a, mu_away)
            for h in range(15) for a in range(15) if h > a
        )
        return prob_home, 1 - prob_home

    def calc_valor(prob, cuota):
        return round((prob * cuota - 1) * 100, 2)

    def kelly_con_techo(prob, cuota) -> float:
        """
        Kelly fraccionado con techo duro de KELLY_MAX_STAKE_PCT.
        Devuelve el porcentaje de bankroll a apostar (0 – KELLY_MAX_STAKE_PCT).
        """
        if not prob or not cuota or cuota <= 1:
            return 0.0
        b = cuota - 1
        kelly_full = (prob * (b + 1) - 1) / b
        if kelly_full <= 0:
            return 0.0
        stake = kelly_full * KELLY_FRACCION * 100
        return round(min(stake, KELLY_MAX_STAKE_PCT), 2)

    def prob_total(mu_total, linea, pick):
        """
        Probabilidad Poisson de que el total de carreras supere (Over)
        o quede por debajo (Under) de la línea.
        Usa distribución de la suma de dos Poisson independientes.
        """
        if pick == 'Over':
            # P(X > linea) donde X ~ Poisson(mu_total)
            return float(poisson.sf(linea, mu_total))
        else:
            # P(X < linea) — excluye el push (X == linea)
            return float(poisson.cdf(linea - 1, mu_total))

    for partido in partidos:
        hs  = partido['home_stats']
        as_ = partido['away_stats']
        ho  = partido['home_team']
        aw  = partido['away_team']

        rph   = partido.get('home_offense', {}).get('runs_last_5', 4.5)
        rpa   = partido.get('away_offense', {}).get('runs_last_5', 4.5)
        era_a = as_['ERA']
        era_h = hs['ERA']

        adj_home = rph * (2 - era_a / 5)
        adj_away = rpa * (2 - era_h / 5)

        proj_home  = round(adj_home, 2)
        proj_away  = round(adj_away, 2)
        total_proj = proj_home + proj_away

        prob_home, prob_away = simular_prob_ganar(proj_home, proj_away)

        ml_h     = partido.get("cuota_home")
        ml_a     = partido.get("cuota_away")
        rl_h     = partido.get("cuota_rl_home")
        rl_a     = partido.get("cuota_rl_away")
        ou_line  = partido.get("linea_total")
        ou_over  = partido.get("cuota_over")
        ou_under = partido.get("cuota_under")

        # Usar proyecciones del pipeline completo si están disponibles
        proj_home  = partido.get('proj_home', proj_home)
        proj_away  = partido.get('proj_away', proj_away)
        total_proj = proj_home + proj_away

        # Inicializar todos los campos
        partido.update({
            'proj_home':       proj_home,
            'proj_away':       proj_away,
            'prob_home_win':   round(prob_home, 3),
            'prob_away_win':   round(prob_away, 3),
            'linea_total':     ou_line,
            'cuota_over':      ou_over,
            'cuota_under':     ou_under,
            'pick_total':      "Sin ventaja clara",
            'valor_total':     0.0,
            'stake_pct_total': 0.0,   # ← nuevo campo
            'pick_ml':         "Sin datos",
            'valor_ml':        0.0,
            'pick_rl':         "Sin datos",
            'valor_rl':        0.0,
            'mejor_pick':      "Ninguno",
            'kelly_ml':        0.0,
            'kelly_rl':        0.0,
            'stake_pct_ml':    0.0,
            'stake_pct_rl':    0.0,
        })

        predicciones = []

        # ── ML ────────────────────────────────────────────────────────────────
        if ml_h and ml_a:
            val_home = calc_valor(prob_home, ml_h)
            val_away = calc_valor(prob_away, ml_a)

            if val_home >= val_away:
                pick_ml, val_ml, prob_ml, cuota_ml = ho, val_home, prob_home, ml_h
            else:
                pick_ml, val_ml, prob_ml, cuota_ml = aw, val_away, prob_away, ml_a

            stake_ml = kelly_con_techo(prob_ml, cuota_ml)
            partido.update({
                'pick_ml':      pick_ml,
                'valor_ml':     val_ml,
                'kelly_ml':     stake_ml,
                'stake_pct_ml': stake_ml,
            })
            predicciones.append({
                'mercado': 'ML', 'seleccion': pick_ml,
                'valor': val_ml, 'prob': round(prob_ml, 3),
                'cuota': cuota_ml, 'stake_pct': stake_ml,
            })

        # ── RL ────────────────────────────────────────────────────────────────
        if rl_h and rl_a:
            pick_rl_team = ho if prob_home > prob_away else aw
            rl_cuota     = rl_h if pick_rl_team == ho else rl_a
            rl_prob      = prob_home if pick_rl_team == ho else prob_away
            val_rl       = calc_valor(rl_prob, rl_cuota)
            stake_rl     = kelly_con_techo(rl_prob, rl_cuota)

            partido.update({
                'pick_rl':      pick_rl_team,
                'valor_rl':     val_rl,
                'kelly_rl':     stake_rl,
                'stake_pct_rl': stake_rl,
            })
            predicciones.append({
                'mercado': 'RL', 'seleccion': pick_rl_team,
                'valor': val_rl, 'prob': round(rl_prob, 3),
                'cuota': rl_cuota, 'stake_pct': stake_rl,
            })

        # ── Totales con Kelly ─────────────────────────────────────────────────
        if ou_line and ou_over and ou_under:
            diff = total_proj - ou_line

            if abs(diff) >= 1.0:
                pick_t  = 'Over' if diff > 0 else 'Under'
                cuota_t = ou_over if pick_t == 'Over' else ou_under

                # Probabilidad Poisson del total proyectado
                mu_total = max(total_proj, 0.1)
                p_total  = prob_total(mu_total, ou_line, pick_t)

                valor_t  = calc_valor(p_total, cuota_t)

                # Kelly para totales — mismo mecanismo que ML/RL
                # Solo asignar stake si la probabilidad supera el umbral mínimo
                stake_t = 0.0
                if p_total >= UMBRAL_PROB_TOTAL and valor_t >= UMBRAL_VALOR_TOTAL:
                    stake_t = kelly_con_techo(p_total, cuota_t)

                partido.update({
                    'pick_total':      pick_t,
                    'valor_total':     valor_t,
                    'stake_pct_total': stake_t,
                })
                predicciones.append({
                    'mercado': 'TOTAL', 'seleccion': pick_t,
                    'valor': valor_t, 'prob': round(p_total, 3),
                    'cuota': cuota_t, 'stake_pct': stake_t,
                })
            else:
                partido['valor_total'] = 0.0
        else:
            partido['valor_total'] = 0.0

        partido['predicciones'] = predicciones

        # ── Elegir mejor pick ─────────────────────────────────────────────────
        mejor_valor  = -999
        mejor_opcion = "Ninguno"

        # ML
        if (partido['valor_ml'] >= UMBRAL_VALOR_ML
                and ml_h and MIN_CUOTA_ACEPTADA <= ml_h <= MAX_CUOTA_ACEPTADA
                and partido['prob_home_win'] >= UMBRAL_PROB_MIN):
            mejor_valor  = partido['valor_ml']
            mejor_opcion = f"ML: {partido['pick_ml']}"

        # RL
        if (partido['valor_rl'] >= UMBRAL_VALOR_RL
                and rl_h and MIN_CUOTA_ACEPTADA <= rl_h <= MAX_CUOTA_ACEPTADA
                and partido['prob_home_win'] >= UMBRAL_PROB_MIN
                and partido['valor_rl'] > mejor_valor):
            mejor_valor  = partido['valor_rl']
            mejor_opcion = f"RL: {partido['pick_rl']}"

        # TOTAL — ahora compite con ML y RL en la selección del mejor pick
        # Solo entra si tiene stake asignado (prob >= umbral y valor >= umbral)
        if (partido['stake_pct_total'] > 0
                and partido['valor_total'] > mejor_valor):
            mejor_valor  = partido['valor_total']
            mejor_opcion = f"TOTAL: {partido['pick_total']}"

        partido['mejor_pick'] = mejor_opcion

    return partidos