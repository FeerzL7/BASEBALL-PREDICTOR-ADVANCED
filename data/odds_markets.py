"""
Market keys supported by The Odds API.

Featured markets can be requested from /sports/{sport}/odds. Additional,
period and player-prop markets must be requested one event at a time from
/sports/{sport}/events/{eventId}/odds.
"""

FEATURED_MARKETS = {
    "h2h",       # Head to head / moneyline / 1x2
    "spreads",  # Point spreads / handicap
    "totals",   # Over/under
}

MARKET_GROUPS = {
    "core": [
        "h2h",
        "spreads",
        "totals",
    ],
    "baseball_game": [
        "alternate_spreads",
        "alternate_totals",
        "h2h_3_way",
        "team_totals",
        "alternate_team_totals",
    ],
    "baseball_periods": [
        "h2h_1st_1_innings",
        "h2h_1st_3_innings",
        "h2h_1st_5_innings",
        "h2h_1st_7_innings",
        "h2h_3_way_1st_1_innings",
        "h2h_3_way_1st_3_innings",
        "h2h_3_way_1st_5_innings",
        "h2h_3_way_1st_7_innings",
        "spreads_1st_1_innings",
        "spreads_1st_3_innings",
        "spreads_1st_5_innings",
        "spreads_1st_7_innings",
        "alternate_spreads_1st_1_innings",
        "alternate_spreads_1st_3_innings",
        "alternate_spreads_1st_5_innings",
        "alternate_spreads_1st_7_innings",
        "totals_1st_1_innings",
        "totals_1st_3_innings",
        "totals_1st_5_innings",
        "totals_1st_7_innings",
        "alternate_totals_1st_1_innings",
        "alternate_totals_1st_3_innings",
        "alternate_totals_1st_5_innings",
        "alternate_totals_1st_7_innings",
    ],
    "team_periods": [
        "team_totals_h1",
        "team_totals_h2",
        "team_totals_q1",
        "team_totals_q2",
        "team_totals_q3",
        "team_totals_q4",
        "alternate_team_totals_h1",
        "alternate_team_totals_h2",
        "alternate_team_totals_q1",
        "alternate_team_totals_q2",
        "alternate_team_totals_q3",
        "alternate_team_totals_q4",
    ],
    "mlb_player_props": [
        "batter_home_runs",
        "batter_first_home_run",
        "batter_hits",
        "batter_total_bases",
        "batter_rbis",
        "batter_runs_scored",
        "batter_hits_runs_rbis",
        "batter_singles",
        "batter_doubles",
        "batter_triples",
        "batter_walks",
        "batter_strikeouts",
        "batter_stolen_bases",
        "pitcher_strikeouts",
        "pitcher_record_a_win",
        "pitcher_hits_allowed",
        "pitcher_walks",
        "pitcher_earned_runs",
        "pitcher_outs",
    ],
    "mlb_alternate_props": [
        "batter_total_bases_alternate",
        "batter_home_runs_alternate",
        "batter_hits_alternate",
        "batter_rbis_alternate",
        "batter_walks_alternate",
        "batter_strikeouts_alternate",
        "batter_runs_scored_alternate",
        "batter_singles_alternate",
        "batter_doubles_alternate",
        "batter_triples_alternate",
        "pitcher_hits_allowed_alternate",
        "pitcher_walks_alternate",
        "pitcher_earned_runs_alternate",
        "pitcher_strikeouts_alternate",
        "pitcher_outs_alternate",
    ],
    "non_mlb": [
        "btts",
        "draw_no_bet",
    ],
}

UNSUPPORTED_REQUESTED_MARKETS = {
    "team_totals_1st_5_innings": (
        "The Odds API market list does not currently expose a baseball-specific "
        "team_totals_1st_5_innings key. Use team_totals when available, or "
        "monitor future API additions."
    ),
    "batter_walks_assists": (
        "MLB docs expose batter_walks, not batter walks + assists."
    ),
}


def expand_market_groups(groups: str | list[str] | None) -> list[str]:
    if not groups:
        groups = ["core"]
    if isinstance(groups, str):
        groups = [g.strip() for g in groups.split(",") if g.strip()]

    markets: list[str] = []
    seen = set()
    for group in groups:
        keys = MARKET_GROUPS.get(group, [group])
        for key in keys:
            if key not in seen:
                markets.append(key)
                seen.add(key)
    return markets


def split_featured_and_event_markets(markets: list[str]) -> tuple[list[str], list[str]]:
    featured = [m for m in markets if m in FEATURED_MARKETS]
    event = [m for m in markets if m not in FEATURED_MARKETS]
    return featured, event


def chunk_markets(markets: list[str], chunk_size: int = 12) -> list[list[str]]:
    return [markets[i:i + chunk_size] for i in range(0, len(markets), chunk_size)]
