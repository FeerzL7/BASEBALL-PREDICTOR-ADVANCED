from statsapi import lookup_team, get

def analizar_defensiva(partidos):
    for p in partidos:
        for equipo_key in ['home_team', 'away_team']:
            team_name = p[equipo_key]
            try:
                team_id = lookup_team(team_name)[0]['id']
                stats = get("team_stats", {
                    "teamId": team_id,
                    "group": "fielding",
                    "stats": "season"
                })
                fielding = stats['stats'][0]['splits'][0]['stat']
                errores = int(fielding.get('errors', 0))
                dp = int(fielding.get('doublePlays', 0))
                fpct = float(fielding.get('fieldingPercentage', 0.980))

                # Optional: calcular errores recientes
                games = get("team_game_logs", {
                    "teamId": team_id,
                    "season": 2024,
                    "limit": 10
                })

                errores_recientes = 0
                for g in games.get("stats", []):
                    errores_juego = int(g['stat'].get('errors', 0))
                    errores_recientes += errores_juego

                p[f'{equipo_key}_defense'] = {
                    'errores': errores,
                    'errores_ult10': errores_recientes,
                    'dp': dp,
                    'fpct': fpct
                }
            except:
                p[f'{equipo_key}_defense'] = {
                    'errores': 10,
                    'errores_ult10': 5,
                    'dp': 10,
                    'fpct': 0.975
                }
    return partidos