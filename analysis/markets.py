# analysis/markets.py
import difflib
import unicodedata
from difflib import SequenceMatcher
from utils.logger import get as get_log

log = get_log()


def normalizar(texto):
    if not texto:
        return ''
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode('utf-8')
    return texto.lower().strip()


def match_nombre_equipo(nombre, lista_opciones):
    nombre_normalizado = normalizar(nombre)
    mejor_match = None
    mejor_score = 0.0
    for opcion in lista_opciones:
        score = SequenceMatcher(None, nombre_normalizado, normalizar(opcion)).ratio()
        if score > mejor_score and score > 0.6:
            mejor_score = score
            mejor_match = opcion
    return mejor_match


def extraer_mejores_cuotas(evento, mercado_clave):
    try:
        mercados = evento["bookmakers"]
        mejores = {
            "over": None, "under": None,
            "home": None, "away": None, "total_line": None
        }

        for book in mercados:
            for market in book.get("markets", []):
                if market["key"] != mercado_clave:
                    continue
                for outcome in market.get("outcomes", []):
                    name  = outcome.get("name", "").lower()
                    price = outcome.get("price")
                    point = outcome.get("point", None)
                    if price is None:
                        continue

                    if mercado_clave == "totals":
                        if "over" in name:
                            if mejores["over"] is None or price > mejores["over"]:
                                mejores["over"]       = price
                                mejores["total_line"] = point
                        elif "under" in name:
                            if mejores["under"] is None or price > mejores["under"]:
                                mejores["under"]      = price
                                mejores["total_line"] = point
                        else:
                            log.debug(f"Resultado inesperado en totals: {name}")

                    elif mercado_clave in ("h2h", "spreads"):
                        if normalizar(name) == normalizar(evento['home_team']):
                            if mejores["home"] is None or price > mejores["home"]:
                                mejores["home"] = price
                        elif normalizar(name) == normalizar(evento['away_team']):
                            if mejores["away"] is None or price > mejores["away"]:
                                mejores["away"] = price

        return mejores

    except Exception as e:
        log.error(f"Al extraer cuotas ({mercado_clave}): {e}")
        return {"over": None, "under": None,
                "home": None, "away": None, "total_line": None}


def extraer_mercados_disponibles(evento: dict) -> dict:
    """
    Normaliza todos los mercados cargados para uso futuro.

    Estructura:
      {
        "pitcher_strikeouts": [
          {"bookmaker": "FanDuel", "name": "Pitcher", "price": 1.91,
           "point": 5.5, "description": "Player Name"}
        ]
      }
    """
    mercados: dict = {}
    for book in evento.get("bookmakers", []):
        book_title = book.get("title") or book.get("key")
        for market in book.get("markets", []):
            key = market.get("key")
            if not key:
                continue
            for outcome in market.get("outcomes", []):
                price = outcome.get("price")
                if price is None:
                    continue
                mercados.setdefault(key, []).append({
                    "bookmaker": book_title,
                    "name": outcome.get("name"),
                    "price": price,
                    "point": outcome.get("point"),
                    "description": outcome.get("description"),
                    "last_update": market.get("last_update"),
                })
    return mercados


def extraer_mejores_por_mercado(evento: dict) -> dict:
    mejores = {}
    for key, outcomes in extraer_mercados_disponibles(evento).items():
        por_outcome = {}
        for item in outcomes:
            selector = (
                item.get("description") or "",
                item.get("name") or "",
                item.get("point"),
            )
            actual = por_outcome.get(selector)
            if actual is None or item["price"] > actual["price"]:
                por_outcome[selector] = item
        mejores[key] = list(por_outcome.values())
    return mejores


def analizar_mercados(partidos, cuotas_api):
    log.debug("Procesando mercados de apuestas...")

    eventos       = cuotas_api
    equipos_ev    = [f"{ev['home_team']} vs {ev['away_team']}" for ev in eventos]

    for partido in partidos:
        home = partido["home_team"]
        away = partido["away_team"]

        nombre_match = match_nombre_equipo(f"{home} vs {away}", equipos_ev)
        evento = None

        if nombre_match:
            for ev in eventos:
                if normalizar(f"{ev['home_team']} vs {ev['away_team']}") == \
                   normalizar(nombre_match):
                    evento = ev
                    break

        if not evento:
            log.debug(f"Sin evento de cuotas para: {home} vs {away}")
            partido["cuota_home"]    = None
            partido["cuota_away"]    = None
            partido["cuota_rl_home"] = None
            partido["cuota_rl_away"] = None
            partido["cuota_over"]    = None
            partido["cuota_under"]   = None
            partido["linea_total"]   = None
            partido["odds_event_id"] = None
            partido["odds_markets"] = {}
            partido["odds_best"] = {}
            continue

        partido["odds_event_id"] = evento.get("id")
        partido["odds_loaded"] = evento.get("event_odds_loaded", [])
        partido["odds_markets"] = extraer_mercados_disponibles(evento)
        partido["odds_best"] = extraer_mejores_por_mercado(evento)

        ml  = extraer_mejores_cuotas(evento, "h2h")
        partido["cuota_home"] = ml["home"]
        partido["cuota_away"] = ml["away"]

        rl  = extraer_mejores_cuotas(evento, "spreads")
        partido["cuota_rl_home"] = rl["home"]
        partido["cuota_rl_away"] = rl["away"]

        tot = extraer_mejores_cuotas(evento, "totals")
        if tot.get("over") is not None and \
           tot.get("under") is not None and \
           tot.get("total_line") is not None:
            partido["cuota_over"]  = tot["over"]
            partido["cuota_under"] = tot["under"]
            partido["linea_total"] = tot["total_line"]
        else:
            log.debug(f"Cuotas de totales incompletas para {home} vs {away}")
            partido["cuota_over"]  = None
            partido["cuota_under"] = None
            partido["linea_total"] = None

    return partidos
