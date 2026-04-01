# analysis/value.py

# ── Configuración de gestión de riesgo ────────────────────────────────────────
KELLY_MAX_STAKE_PCT = 5.0   # Techo: nunca más del 5 % del bankroll por pick
KELLY_FRACCION      = 0.5   # Kelly fraccionado (conservador)

# ── Umbrales de valor esperado por mercado ────────────────────────────────────
UMBRAL_VALOR_ML    = 5
UMBRAL_VALOR_RL    = 7
UMBRAL_VALOR_TOTAL = 4

# ── Filtros de calidad ────────────────────────────────────────────────────────
UMBRAL_PROB_MIN    = 0.40
MIN_CUOTA_ACEPTADA = 1.65
MAX_CUOTA_ACEPTADA = 2.50


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

    def kelly_con_techo(prob, cuota):
        """
        Kelly fraccionado con techo duro de KELLY_MAX_STAKE_PCT.
        Devuelve el porcentaje de bankroll a apostar (0–KELLY_MAX_STAKE_PCT).
        """
        if not prob or not cuota or cuota <= 1:
            return 0.0
        b = cuota - 1
        kelly_full = (prob * (b + 1) - 1) / b
        if kelly_full <= 0:
            return 0.0
        stake = kelly_full * KELLY_FRACCION * 100          # % bankroll
        stake = min(stake, KELLY_MAX_STAKE_PCT)             # aplicar techo
        return round(stake, 2)

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

        # Inicializar campos
        partido.update({
            'proj_home':      proj_home,
            'proj_away':      proj_away,
            'prob_home_win':  round(prob_home, 3),
            'prob_away_win':  round(prob_away, 3),
            'linea_total':    ou_line,
            'cuota_over':     ou_over,
            'cuota_under':    ou_under,
            'pick_total':     "Sin ventaja clara",
            'pick_ml':        "Sin datos",
            'valor_ml':       0.0,
            'pick_rl':        "Sin datos",
            'valor_rl':       0.0,
            'mejor_pick':     "Ninguno",
            'kelly_ml':       0.0,
            'kelly_rl':       0.0,
            'stake_pct_ml':   0.0,
            'stake_pct_rl':   0.0,
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
                'mercado':    'ML',
                'seleccion':  pick_ml,
                'valor':      val_ml,
                'prob':       round(prob_ml, 3),
                'cuota':      cuota_ml,
                'stake_pct':  stake_ml,
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
                'mercado':    'RL',
                'seleccion':  pick_rl_team,
                'valor':      val_rl,
                'prob':       round(rl_prob, 3),
                'cuota':      rl_cuota,
                'stake_pct':  stake_rl,
            })

        # ── Totales ───────────────────────────────────────────────────────────
        valor_total = 0.0
        if ou_line and ou_over and ou_under:
            diff = total_proj - ou_line
            if abs(diff) >= 1.0:
                pick_t  = 'Over' if diff > 0 else 'Under'
                cuota_t = ou_over if pick_t == 'Over' else ou_under
                prob_t  = (poisson.sf(ou_line, total_proj)
                           if pick_t == 'Over'
                           else poisson.cdf(ou_line, total_proj))
                valor_total = calc_valor(prob_t, cuota_t)
                partido['pick_total'] = pick_t
                partido['valor_total'] = valor_total
                predicciones.append({
                    'mercado':    'TOTAL',
                    'seleccion':  pick_t,
                    'valor':      valor_total,
                    'prob':       round(prob_t, 3),
                    'cuota':      cuota_t,
                    'stake_pct':  0.0,   # Totales no usan Kelly en este modelo
                })
            else:
                partido['valor_total'] = 0.0
        else:
            partido['valor_total'] = 0.0

        partido['predicciones'] = predicciones

        # ── Elegir mejor pick ─────────────────────────────────────────────────
        mejor_valor  = -999
        mejor_opcion = "Ninguno"

        if (partido['valor_ml'] >= UMBRAL_VALOR_ML
                and ml_h and MIN_CUOTA_ACEPTADA <= ml_h <= MAX_CUOTA_ACEPTADA
                and partido['prob_home_win'] >= UMBRAL_PROB_MIN):
            mejor_valor  = partido['valor_ml']
            mejor_opcion = f"ML: {partido['pick_ml']}"

        if (partido['valor_rl'] >= UMBRAL_VALOR_RL
                and rl_h and MIN_CUOTA_ACEPTADA <= rl_h <= MAX_CUOTA_ACEPTADA
                and partido['prob_home_win'] >= UMBRAL_PROB_MIN
                and partido['valor_rl'] > mejor_valor):
            mejor_valor  = partido['valor_rl']
            mejor_opcion = f"RL: {partido['pick_rl']}"

        if (partido['valor_total'] >= UMBRAL_VALOR_TOTAL
                and partido['valor_total'] > mejor_valor):
            mejor_opcion = f"TOTAL: {partido['pick_total']}"

        partido['mejor_pick'] = mejor_opcion

    return partidos