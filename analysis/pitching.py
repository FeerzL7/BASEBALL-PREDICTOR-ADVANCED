def analizar_pitchers():
    from statsapi import schedule, lookup_player, player_stat_data, get
    from datetime import datetime

    def get_pitcher_stats(name):
        try:
            data = lookup_player(name)
            if not data:
                return {'ERA': 4.5, 'WHIP': 1.3, 'K9': 8.0, 'IP': 0, 'throws': 'R'}
            player_id = data[0]['id']
            stats = player_stat_data(player_id, group='pitching', type='season')
            statline = stats['stats'][0]['stats']
            innings = float(statline.get('inningsPitched', 0))
            throws = get("people", {"personIds": player_id})['people'][0]['pitchHand']['code']
            return {
                'ERA': float(statline.get('era', 4.5)),
                'WHIP': float(statline.get('whip', 1.3)),
                'K9': float(statline.get('strikeOutsPer9Inn', 8.0)),
                'IP': innings,
                'throws': throws
            }
        except:
            return {'ERA': 4.5, 'WHIP': 1.3, 'K9': 8.0, 'IP': 0, 'throws': 'R'}

    today = datetime.now().strftime('%Y-%m-%d')
    sched = schedule(date=today)
    partidos = []
    for juego in sched:
        home = juego['home_name']
        away = juego['away_name']
        home_p = juego.get('home_probable_pitcher', 'Desconocido')
        away_p = juego.get('away_probable_pitcher', 'Desconocido')

        home_stats = get_pitcher_stats(home_p)
        away_stats = get_pitcher_stats(away_p)

        partidos.append({
            'home_team': home,
            'away_team': away,
            'home_pitcher': home_p,
            'home_stats': home_stats,
            'away_pitcher': away_p,
            'away_stats': away_stats,
            'start_time': juego['game_datetime'][:19]
        })
    return partidos