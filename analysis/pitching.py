# analysis/pitching.py

TBD_NOMBRES = {
    '', 'desconocido', 'tbd', 'to be determined',
    'unknown', 'por definir', 'tba'
}

def _es_tbd(nombre):
    """Devuelve True solo si el nombre indica que el lanzador no está anunciado."""
    return not nombre or nombre.strip().lower() in TBD_NOMBRES


def analizar_pitchers():
    from statsapi import schedule, lookup_player, player_stat_data, get
    from datetime import datetime
    from analysis.bullpen import obtener_bullpen

    def get_pitcher_stats(name):
        # Caso 1: nombre vacío o TBD → no confirmado
        if _es_tbd(name):
            return {
                'ERA': 4.5, 'WHIP': 1.3, 'K9': 8.0,
                'IP': 0, 'throws': 'R', 'confirmado': False
            }

        # Caso 2: nombre válido → intentar obtener stats.
        # Si la API falla, el lanzador sigue siendo confirmado;
        # solo usamos defaults como fallback de stats.
        try:
            data = lookup_player(name)
            if not data:
                print(f"[WARNING] Lanzador '{name}' no encontrado en MLB API, tratando como TBD.")
                return {
                    'ERA': 4.5, 'WHIP': 1.3, 'K9': 8.0,
                    'IP': 0, 'throws': 'R', 'confirmado': False
                }

            player_id = data[0]['id']

            try:
                stats    = player_stat_data(player_id, group='pitching', type='season')
                statline = stats['stats'][0]['stats']
                innings  = float(statline.get('inningsPitched', 0))
            except Exception:
                statline = {}
                innings  = 0

            try:
                throws = get("people", {"personIds": player_id})['people'][0]['pitchHand']['code']
            except Exception:
                throws = 'R'

            return {
                'ERA':        float(statline.get('era', 4.5) or 4.5),
                'WHIP':       float(statline.get('whip', 1.3) or 1.3),
                'K9':         float(statline.get('strikeOutsPer9Inn', 8.0) or 8.0),
                'IP':         innings,
                'throws':     throws,
                'confirmado': True,
            }

        except Exception as e:
            print(f"[WARNING] Error obteniendo stats de '{name}': {e}. Usando defaults.")
            return {
                'ERA': 4.5, 'WHIP': 1.3, 'K9': 8.0,
                'IP': 0, 'throws': 'R', 'confirmado': True
            }

    today = datetime.now().strftime('%Y-%m-%d')
    sched = schedule(date=today)
    partidos = []

    for juego in sched:
        home   = juego['home_name']
        away   = juego['away_name']
        home_p = (juego.get('home_probable_pitcher') or '').strip()
        away_p = (juego.get('away_probable_pitcher') or '').strip()

        home_stats = get_pitcher_stats(home_p)
        away_stats = get_pitcher_stats(away_p)

        if not home_p:
            home_p = 'TBD'
        if not away_p:
            away_p = 'TBD'

        ambos_confirmados = home_stats['confirmado'] and away_stats['confirmado']

        if not ambos_confirmados:
            motivo = []
            if not home_stats['confirmado']:
                motivo.append(f"home: {home_p}")
            if not away_stats['confirmado']:
                motivo.append(f"away: {away_p}")
            print(f"[TBD] {home} vs {away} — lanzador no confirmado ({', '.join(motivo)})")

        # Obtener stats de bullpen para ambos equipos
        home_bullpen = obtener_bullpen(home)
        away_bullpen = obtener_bullpen(away)

        partidos.append({
            'home_team':            home,
            'away_team':            away,
            'home_pitcher':         home_p,
            'home_stats':           home_stats,
            'away_pitcher':         away_p,
            'away_stats':           away_stats,
            'home_bullpen':         home_bullpen,
            'away_bullpen':         away_bullpen,
            'start_time':           juego['game_datetime'][:19],
            'pitchers_confirmados': ambos_confirmados,
        })

    return partidos