# analysis/offense.py

def analizar_ofensiva(partidos):
    from statsapi import lookup_team, get
    import numpy as np

    DEFAULTS_VS_R = {'runsPerGame': 4.50, 'OPS': 0.730, 'wRC+': 100, 'runs_last_5': 4.50}
    DEFAULTS_VS_L = {'runsPerGame': 4.30, 'OPS': 0.710, 'wRC+':  96, 'runs_last_5': 4.30}

    def _defaults(vs_hand):
        return dict(DEFAULTS_VS_L if vs_hand == 'L' else DEFAULTS_VS_R)

    def _runs_recientes(team_id, n=10):
        """Promedio de carreras anotadas en los últimos n juegos del schedule."""
        try:
            from datetime import datetime, timedelta
            from statsapi import schedule
            hoy   = datetime.now().strftime('%Y-%m-%d')
            hace  = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d')
            juegos = schedule(start_date=hace, end_date=hoy, teamId=team_id)
            runs = []
            for j in juegos:
                if j.get('status') not in ('Final', 'Game Over'):
                    continue
                if str(j.get('home_id')) == str(team_id):
                    runs.append(int(j.get('home_score', 0) or 0))
                else:
                    runs.append(int(j.get('away_score', 0) or 0))
            runs = runs[-n:]
            return round(float(np.mean(runs)), 3) if runs else 4.5
        except Exception:
            return 4.5

    def _stats_generales(team_id, season=2025):
        """Stats de bateo de temporada completa."""
        try:
            data = get('team_stats', {
                'teamId': team_id,
                'stats':  'season',
                'group':  'hitting',
                'season': season,
            })
            return data['stats'][0]['splits'][0]['stat']
        except Exception:
            return {}

    def _stats_split_vs_hand(team_id, vs_hand, season=2025):
        """
        Intenta obtener stats de bateo vs zurdo o derecho usando sitCodes.
        vs. RHP = sitCode 'vr', vs. LHP = sitCode 'vl'
        Requiere stats=statSplits junto con sitCodes.
        """
        sit_code = 'vr' if vs_hand == 'R' else 'vl'
        try:
            data = get('team_stats', {
                'teamId':   team_id,
                'stats':    'statSplits',
                'sitCodes': sit_code,
                'group':    'hitting',
                'season':   season,
            })
            splits = data.get('stats', [])
            for group in splits:
                for split in group.get('splits', []):
                    stat = split.get('stat', {})
                    if stat and stat.get('ops') is not None:
                        return stat
            return None
        except Exception:
            return None

    def obtener_stats_ofensivas(team_name, vs_hand='R'):
        try:
            team_id = lookup_team(team_name)[0]['id']
        except Exception:
            return _defaults(vs_hand)

        # Carreras recientes siempre desde el schedule (más confiable)
        runs_recientes = _runs_recientes(team_id)

        # Intentar split específico primero, luego stats generales
        stat = _stats_split_vs_hand(team_id, vs_hand)
        if not stat:
            stat = _stats_generales(team_id)

        if not stat:
            d = _defaults(vs_hand)
            d['runs_last_5'] = runs_recientes
            return d

        ops = float(stat.get('ops', 0.730) or 0.730)
        avg = float(stat.get('battingAverage', 0.250) or 0.250)
        rpg = float(stat.get('runsPerGame', runs_recientes) or runs_recientes)

        # Si el RPG de la API es 0 (dato no calculado), usar el promedio reciente
        if rpg == 0:
            rpg = runs_recientes

        # Ajustar runs_last_5 si el split muestra OPS distinto al general
        stat_gen   = _stats_generales(team_id)
        ops_gen    = float(stat_gen.get('ops', ops) or ops) if stat_gen else ops
        if ops_gen > 0 and abs(ops - ops_gen) > 0.010:
            runs_recientes = round(runs_recientes * (ops / ops_gen), 3)

        return {
            'runsPerGame': round(rpg, 3),
            'OPS':         round(ops, 3),
            'wRC+':        round(avg * 400, 1),
            'runs_last_5': max(runs_recientes, 1.5),  # piso de seguridad
            'split':       f"vs{'RHP' if vs_hand == 'R' else 'LHP'}",
        }

    for partido in partidos:
        home = partido['home_team']
        away = partido['away_team']

        # El lineup home batea vs el abridor visitante
        hand_vs_home = partido['away_stats']['throws']
        # El lineup away batea vs el abridor local
        hand_vs_away = partido['home_stats']['throws']

        partido['home_offense'] = obtener_stats_ofensivas(home, hand_vs_home)
        partido['away_offense'] = obtener_stats_ofensivas(away, hand_vs_away)

        print(
            f"[OFFENSE] {home} ({partido['home_offense']['split']} "
            f"OPS={partido['home_offense']['OPS']} "
            f"R/5={partido['home_offense']['runs_last_5']}) | "
            f"{away} ({partido['away_offense']['split']} "
            f"OPS={partido['away_offense']['OPS']} "
            f"R/5={partido['away_offense']['runs_last_5']})"
        )

    return partidos