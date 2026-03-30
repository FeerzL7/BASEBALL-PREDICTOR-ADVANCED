from statsapi import get, lookup_team

def analizar_h2h(partidos):
    for p in partidos:
        home = p['home_team']
        away = p['away_team']
        try:
            home_id = lookup_team(home)[0]['id']
            away_id = lookup_team(away)[0]['id']

            juegos_home = get("team_game_logs", {
                "teamId": home_id,
                "opponentTeamId": away_id,
                "season": 2024,
                "limit": 10
            })

            juegos_away = get("team_game_logs", {
                "teamId": away_id,
                "opponentTeamId": home_id,
                "season": 2024,
                "limit": 10
            })

            runs_home = [int(j['stat'].get('runs', 0)) for j in juegos_home.get("stats", [])]
            runs_away = [int(j['stat'].get('runs', 0)) for j in juegos_away.get("stats", [])]

            p['h2h'] = {
                'partidos': len(runs_home),
                'runs_home_prom': round(sum(runs_home) / len(runs_home), 2) if runs_home else 4.5,
                'runs_away_prom': round(sum(runs_away) / len(runs_away), 2) if runs_away else 4.5
            }
        except:
            p['h2h'] = {
                'partidos': 0,
                'runs_home_prom': 4.5,
                'runs_away_prom': 4.5
            }
    return partidos