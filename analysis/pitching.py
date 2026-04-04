# analysis/pitching.py
#
# Para cada abridor calcula dos tipos de stats:
#
#   stats de temporada  — ERA/WHIP/K9 acumulados (tendencia larga)
#   stats recientes     — ERA ponderada de las últimas N_SALIDAS salidas
#                         (estado actual del pitcher)
#
# ERA efectiva usada en proyecciones:
#   ERA_efectiva = ERA_temporada * PESO_TEMPORADA
#                + ERA_reciente  * PESO_RECIENTE
#
# Si el pitcher no tiene salidas recientes suficientes (ej: lesión, novato),
# se usa solo la ERA de temporada con confirmado=True para no excluir el partido.

from statsapi import schedule, lookup_player, player_stat_data, get
from datetime import datetime
from utils.logger import get as get_log

log = get_log()

# Cuántas salidas recientes considerar
N_SALIDAS = 3

# Peso en la ERA efectiva final
PESO_TEMPORADA = 0.60
PESO_RECIENTE  = 0.40

# Solo considerar salidas donde lanzó al menos este número de innings
IP_MIN_SALIDA  = 1.0

# Nombres que indican lanzador no anunciado
TBD_NOMBRES = {
    '', 'desconocido', 'tbd', 'to be determined',
    'unknown', 'por definir', 'tba'
}


def _es_tbd(nombre: str) -> bool:
    return not nombre or nombre.strip().lower() in TBD_NOMBRES


def _safe_float(val, default: float) -> float:
    try:
        v = float(val)
        return default if (v != v) else v
    except (TypeError, ValueError):
        return default


def _stats_temporada(player_id: int) -> dict:
    """ERA/WHIP/K9 acumulados de la temporada actual."""
    try:
        datos    = player_stat_data(player_id, group='pitching', type='season')
        statline = datos['stats'][0]['stats']
        ip       = _safe_float(statline.get('inningsPitched'), 0.0)
        throws   = get("people", {"personIds": player_id})[# type: ignore
            'people'][0]['pitchHand']['code']
        return {
            'ERA':        _safe_float(statline.get('era'),                4.50),
            'WHIP':       _safe_float(statline.get('whip'),               1.30),
            'K9':         _safe_float(statline.get('strikeOutsPer9Inn'),   8.00),
            'IP':         ip,
            'throws':     throws,
            'confirmado': True,
        }
    except Exception:
        return {
            'ERA': 4.50, 'WHIP': 1.30, 'K9': 8.00,
            'IP': 0, 'throws': 'R', 'confirmado': True,
        }


def _stats_recientes(player_id: int, n: int = N_SALIDAS) -> dict | None:
    """
    Devuelve ERA y WHIP ponderados de las últimas n salidas del pitcher.
    Retorna None si no hay suficientes datos (pitcher nuevo, lesionado, etc.)

    Usa player_stat_data con type='gameLog' — devuelve una entrada por partido.
    Solo cuenta salidas donde el pitcher fue el abridor (gamesStarted=1)
    y lanzó al menos IP_MIN_SALIDA innings.
    """
    try:
        datos   = player_stat_data(player_id, group='pitching', type='gameLog')
        salidas = [
            s['stats'] for s in datos.get('stats', [])
            if s.get('type') == 'gameLog'
            and int(s['stats'].get('gamesStarted', 0) or 0) >= 1
            and _safe_float(s['stats'].get('inningsPitched'), 0.0) >= IP_MIN_SALIDA
        ]
    except Exception as e:
        log.debug(f"gameLog falló para player_id={player_id}: {e}")
        return None

    if not salidas:
        return None

    # Las más recientes primero — statsapi devuelve cronológicamente
    ultimas = salidas[-n:]

    er_sum   = 0.0
    ip_total = 0.0
    h_sum    = 0.0
    bb_sum   = 0.0

    for s in ultimas:
        ip = _safe_float(s.get('inningsPitched'), 0.0)
        er = _safe_float(s.get('earnedRuns'),     0.0)
        h  = _safe_float(s.get('hits'),           0.0)
        bb = _safe_float(s.get('baseOnBalls'),    0.0)

        er_sum   += er
        ip_total += ip
        h_sum    += h
        bb_sum   += bb

    if ip_total == 0:
        return None

    era_rec  = round((er_sum  / ip_total) * 9, 3)
    whip_rec = round((h_sum + bb_sum) / ip_total, 3)

    return {
        'ERA_reciente':  era_rec,
        'WHIP_reciente': whip_rec,
        'IP_reciente':   round(ip_total, 1),
        'n_salidas':     len(ultimas),
    }


def _era_efectiva(era_temp: float, recientes: dict | None) -> float:
    """
    Combina ERA de temporada con ERA reciente.
    Si no hay datos recientes, usa 100% la de temporada.
    """
    if not recientes or recientes['n_salidas'] == 0:
        return era_temp

    era_rec = max(0.50, min(recientes['ERA_reciente'], 12.0))
    era_tmp = max(0.50, min(era_temp, 12.0))

    return round(era_tmp * PESO_TEMPORADA + era_rec * PESO_RECIENTE, 3)


def get_pitcher_stats(name: str) -> dict:
    """
    Punto de entrada: devuelve stats completos del pitcher.
    Incluye ERA efectiva (temporada + últimas salidas).
    """
    if _es_tbd(name):
        return {
            'ERA': 4.50, 'WHIP': 1.30, 'K9': 8.00, 'IP': 0,
            'throws': 'R', 'confirmado': False,
            'ERA_efectiva': 4.50, 'ERA_reciente': None,
            'WHIP_reciente': None, 'n_salidas_recientes': 0,
        }

    try:
        data = lookup_player(name)
        if not data:
            log.warning(f"Lanzador '{name}' no encontrado en MLB API. Tratando como TBD.")
            return {
                'ERA': 4.50, 'WHIP': 1.30, 'K9': 8.00, 'IP': 0,
                'throws': 'R', 'confirmado': False,
                'ERA_efectiva': 4.50, 'ERA_reciente': None,
                'WHIP_reciente': None, 'n_salidas_recientes': 0,
            }

        player_id = data[0]['id']

        # Stats de temporada (siempre primero — fallback robusto)
        temp = _stats_temporada(player_id)

        # Stats recientes (puede fallar silenciosamente)
        recientes = _stats_recientes(player_id)

        era_ef = _era_efectiva(temp['ERA'], recientes)

        resultado = {
            **temp,
            'ERA_efectiva':        era_ef,
            'ERA_reciente':        recientes['ERA_reciente']  if recientes else None,
            'WHIP_reciente':       recientes['WHIP_reciente'] if recientes else None,
            'IP_reciente':         recientes['IP_reciente']   if recientes else 0.0,
            'n_salidas_recientes': recientes['n_salidas']     if recientes else 0,
        }

        # Log informativo
        if recientes:
            log.debug(
                f"{name}: ERA temp={temp['ERA']} | "
                f"ERA últ.{recientes['n_salidas']} sal.={recientes['ERA_reciente']} | "
                f"ERA efectiva={era_ef}"
            )
        else:
            log.debug(f"{name}: ERA temp={temp['ERA']} | sin salidas recientes")

        return resultado

    except Exception as e:
        log.warning(f"Error obteniendo stats de '{name}': {e}. Usando defaults.")
        return {
            'ERA': 4.50, 'WHIP': 1.30, 'K9': 8.00, 'IP': 0,
            'throws': 'R', 'confirmado': True,
            'ERA_efectiva': 4.50, 'ERA_reciente': None,
            'WHIP_reciente': None, 'n_salidas_recientes': 0,
        }


def analizar_pitchers() -> list:
    """Obtiene el schedule del día y las stats de cada abridor probable."""
    from analysis.bullpen import obtener_bullpen

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
            log.warning(
                f"{home} vs {away} — lanzador no confirmado ({', '.join(motivo)})"
            )

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

    log.info(f"Pitchers analizados: {len(partidos)} partidos.")
    return partidos