def analizar_valor(partidos):
    from scipy.stats import poisson
    import numpy as np

    def simular_prob_ganar(mu_home, mu_away):
        prob_home = sum([
            poisson.pmf(h, mu_home) * poisson.pmf(a, mu_away)
            for h in range(15) for a in range(15) if h > a
        ])
        return prob_home, 1 - prob_home

    def calc_valor(prob, cuota):
        return round((prob * cuota - 1) * 100, 2)

    def kelly(prob, cuota):
        frac = (prob * (cuota - 1) - (1 - prob)) / (cuota - 1)
        return round(max(frac, 0), 4)

    # Umbrales de valor esperado por tipo de mercado
    UMBRAL_VALOR_ML = 5
    UMBRAL_VALOR_RL = 7
    UMBRAL_VALOR_TOTAL = 4

    # Filtros adicionales
    UMBRAL_PROB_MIN = 0.40
    MIN_CUOTA_ACEPTADA = 1.65
    MAX_CUOTA_ACEPTADA = 2.50

    # Kelly conservador
    FACTOR_MODERACION = 0.5

    for partido in partidos:
        hs = partido['home_stats']
        as_ = partido['away_stats']
        ho = partido['home_team']
        aw = partido['away_team']

        rph = partido.get('home_offense', {}).get('runs_last_5', 4.5)
        rpa = partido.get('away_offense', {}).get('runs_last_5', 4.5)
        era_a = as_['ERA']
        era_h = hs['ERA']

        adj_home = rph * (2 - era_a / 5)
        adj_away = rpa * (2 - era_h / 5)

        proj_home = round(adj_home, 2)
        proj_away = round(adj_away, 2)
        total_proj = proj_home + proj_away

        prob_home, prob_away = simular_prob_ganar(proj_home, proj_away)

        ml_h = partido.get("cuota_home")
        ml_a = partido.get("cuota_away")
        rl_h = partido.get("cuota_rl_home")
        rl_a = partido.get("cuota_rl_away")
        ou_line = partido.get("linea_total")
        ou_over = partido.get("cuota_over")
        ou_under = partido.get("cuota_under")


        partido['proj_home'] = proj_home
        partido['proj_away'] = proj_away
        partido['prob_home_win'] = round(prob_home, 3)
        partido['prob_away_win'] = round(prob_away, 3)
        partido['linea_total'] = ou_line
        partido['cuota_over'] = ou_over
        partido['cuota_under'] = ou_under

        partido['pick_total'] = "Sin ventaja clara"
        partido['pick_ml'] = "Sin datos"
        partido['valor_ml'] = 0.0
        partido['pick_rl'] = "Sin datos"
        partido['valor_rl'] = 0.0
        partido['mejor_pick'] = "Ninguno"
        partido['kelly_ml'] = 0.0
        partido['kelly_rl'] = 0.0
        partido['stake_pct_ml'] = 0.0
        partido['stake_pct_rl'] = 0.0

        predicciones = []

        # ML
        if ml_h and ml_a:
            val_home = calc_valor(prob_home, ml_h)
            val_away = calc_valor(prob_away, ml_a)

            if val_home > val_away:
                partido['pick_ml'] = ho
                partido['valor_ml'] = val_home
                partido['kelly_ml'] = kelly(prob_home, ml_h)
                partido['stake_pct_ml'] = round(partido['kelly_ml'] * FACTOR_MODERACION * 100, 2)
                predicciones.append({
                    'mercado': 'ML',
                    'selección': ho,
                    'valor': val_home,
                    'prob': round(prob_home, 3),
                    'cuota': ml_h
                })
            else:
                partido['pick_ml'] = aw
                partido['valor_ml'] = val_away
                partido['kelly_ml'] = kelly(prob_away, ml_a)
                partido['stake_pct_ml'] = round(partido['kelly_ml'] * FACTOR_MODERACION * 100, 2)
                predicciones.append({
                    'mercado': 'ML',
                    'selección': aw,
                    'valor': val_away,
                    'prob': round(prob_away, 3),
                    'cuota': ml_a
                })

        # RL
        if rl_h and rl_a:
            pick_rl_team = ho if prob_home > prob_away else aw
            rl_cuota = rl_h if pick_rl_team == ho else rl_a
            rl_prob = prob_home if pick_rl_team == ho else prob_away
            partido['pick_rl'] = pick_rl_team
            partido['valor_rl'] = calc_valor(rl_prob, rl_cuota)
            partido['kelly_rl'] = kelly(rl_prob, rl_cuota)
            partido['stake_pct_rl'] = round(partido['kelly_rl'] * FACTOR_MODERACION * 100, 2)
            predicciones.append({
                'mercado': 'RL',
                'selección': pick_rl_team,
                'valor': partido['valor_rl'],
                'prob': round(rl_prob, 3),
                'cuota': rl_cuota
            })

        # Totales
        if ou_line and ou_over and ou_under:
            diff = total_proj - ou_line
            if abs(diff) >= 1.0:
                pick = 'Over' if diff > 0 else 'Under'
                cuota = ou_over if pick == 'Over' else ou_under
                prob = poisson.sf(ou_line, total_proj) if pick == 'Over' else poisson.cdf(ou_line, total_proj)
                valor = calc_valor(prob, cuota)
                partido['pick_total'] = pick
                partido['valor_total'] = valor
                predicciones.append({
                    'mercado': 'TOTAL',
                    'selección': pick,
                    'valor': valor,
                    'prob': round(prob, 3),
                    'cuota': cuota
                })
            else:
                partido['valor_total'] = 0.0
        else:
            partido['valor_total'] = 0.0

        partido['predicciones'] = predicciones

        # --- Elegir mejor pick con criterios de calidad ---
        mejor_valor = -999
        mejor_opcion = "Ninguno"

        if partido['valor_ml'] >= UMBRAL_VALOR_ML and MIN_CUOTA_ACEPTADA <= ml_h <= MAX_CUOTA_ACEPTADA and partido['prob_home_win'] >= UMBRAL_PROB_MIN:
            mejor_valor = partido['valor_ml']
            mejor_opcion = f"ML: {partido['pick_ml']}"

        if partido['valor_rl'] >= UMBRAL_VALOR_RL and MIN_CUOTA_ACEPTADA <= rl_h <= MAX_CUOTA_ACEPTADA and partido['prob_home_win'] >= UMBRAL_PROB_MIN:
            if partido['valor_rl'] > mejor_valor:
                mejor_valor = partido['valor_rl']
                mejor_opcion = f"RL: {partido['pick_rl']}"

        if partido['valor_total'] >= UMBRAL_VALOR_TOTAL:
            # Aquí no se aplica filtro de probabilidad, solo diferencia de línea
            if partido['valor_total'] > mejor_valor:
                mejor_valor = partido['valor_total']
                mejor_opcion = f"TOTAL: {partido['pick_total']}"

        partido['mejor_pick'] = mejor_opcion

    return partidos
