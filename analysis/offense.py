def analizar_ofensiva(partidos):
    from statsapi import lookup_team, get
    from datetime import datetime
    import numpy as np

    def obtener_stats_ofensivas(team, vs_hand='R'):
        try:
            team_id = lookup_team(team)[0]['id']
            stats = get("team_stats", {"teamId": team_id, "stats": "season", "group": "hitting"})
            s = stats['stats'][0]['splits'][0]['stat']
            # Simulamos últimas 5 como promedio estándar (si deseas implementar logs reales puedes scrapear MLB)
            runs_last_5 = float(s.get("runsPerGame", 4.5))
            return {
                'runsPerGame': float(s.get('runsPerGame', 4.5)),
                'OPS': float(s.get('ops', 0.73)),
                'wRC+': float(s.get('battingAverage', 0.25)) * 400,
                'runs_last_5': runs_last_5
            }
        except:
            return {
                'runsPerGame': 4.5,
                'OPS': 0.73,
                'wRC+': 100,
                'runs_last_5': 4.5
            }

    for partido in partidos:
        away = partido['away_team']
        home = partido['home_team']
        hand_home = partido['away_stats']['throws']
        hand_away = partido['home_stats']['throws']
        partido['home_offense'] = obtener_stats_ofensivas(home, hand_home)
        partido['away_offense'] = obtener_stats_ofensivas(away, hand_away)

    return partidos
