import requests

from data.odds_markets import (
    chunk_markets,
    expand_market_groups,
    split_featured_and_event_markets,
)
from utils.constants import (
    API_KEY,
    MARKETS,
    ODDS_BOOKMAKERS,
    ODDS_EVENT_MARKET_GROUPS,
    ODDS_MARKET_GROUPS,
    REGION,
    SPORT,
)

BASE_URL = "https://api.the-odds-api.com/v4"


def _request_json(url: str, params: dict):
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] No se pudieron obtener cuotas: {e}")
        return None

    try:
        data = response.json()
    except ValueError:
        print("[ERROR] No se pudo decodificar el JSON de la API")
        return None

    if isinstance(data, dict) and data.get("message"):
        print("[ERROR] API Error:", data["message"])
        return None

    return data


def _odds_params(markets: list[str]) -> dict:
    params = {
        "regions": REGION,
        "markets": ",".join(markets),
        "oddsFormat": "decimal",
        "apiKey": API_KEY,
    }
    if ODDS_BOOKMAKERS:
        params.pop("regions", None)
        params["bookmakers"] = ODDS_BOOKMAKERS
    return params


def _merge_event_markets(evento: dict, detalle: dict):
    for detail_book in detalle.get("bookmakers", []):
        book_key = detail_book.get("key")
        book = next(
            (b for b in evento.setdefault("bookmakers", [])
             if b.get("key") == book_key),
            None,
        )
        if book is None:
            book = {
                "key": book_key,
                "title": detail_book.get("title"),
                "markets": [],
            }
            evento["bookmakers"].append(book)

        existing_keys = {m.get("key") for m in book.get("markets", [])}
        for market in detail_book.get("markets", []):
            if market.get("key") in existing_keys:
                continue
            book.setdefault("markets", []).append(market)
            existing_keys.add(market.get("key"))

    loaded = {
        market.get("key")
        for book in evento.get("bookmakers", [])
        for market in book.get("markets", [])
        if market.get("key")
    }
    evento["event_odds_loaded"] = sorted(loaded)


def _configured_markets() -> tuple[list[str], list[str]]:
    explicit_markets = [m.strip() for m in MARKETS.split(",") if m.strip()]
    grouped_markets = expand_market_groups(ODDS_MARKET_GROUPS)
    markets = list(dict.fromkeys(explicit_markets + grouped_markets))
    featured, event_markets = split_featured_and_event_markets(markets)

    extra_event_markets = expand_market_groups(ODDS_EVENT_MARKET_GROUPS)
    _, env_event_markets = split_featured_and_event_markets(extra_event_markets)
    event_markets = list(dict.fromkeys(event_markets + env_event_markets))

    return featured or ["h2h"], event_markets


def obtener_cuotas():
    if not API_KEY:
        print("[ERROR] Configura ODDS_API_KEY o API_KEY en .env para obtener cuotas")
        return []

    featured_markets, event_markets = _configured_markets()
    url = f"{BASE_URL}/sports/{SPORT}/odds"
    data = _request_json(url, _odds_params(featured_markets))
    if not isinstance(data, list):
        return []

    if not event_markets:
        return data

    for evento in data:
        event_id = evento.get("id")
        if not event_id:
            continue
        for chunk in chunk_markets(event_markets):
            detail_url = f"{BASE_URL}/sports/{SPORT}/events/{event_id}/odds"
            detalle = _request_json(detail_url, _odds_params(chunk))
            if isinstance(detalle, dict):
                _merge_event_markets(evento, detalle)

    return data
