# The Odds API Markets

El proyecto mantiene `h2h,spreads,totals` como mercados core del pipeline.
Los mercados avanzados se cargan por evento para ahorrar creditos y evitar
respuestas enormes.

## Configuracion recomendada

Core solamente:

```env
ODDS_MARKET_GROUPS=core
ODDS_EVENT_MARKET_GROUPS=
```

Core + alternativos + innings:

```env
ODDS_MARKET_GROUPS=core,baseball_game,baseball_periods
ODDS_EVENT_MARKET_GROUPS=
```

Core + props MLB:

```env
ODDS_MARKET_GROUPS=core
ODDS_EVENT_MARKET_GROUPS=mlb_player_props,mlb_alternate_props
```

Todo lo disponible para MLB:

```env
ODDS_MARKET_GROUPS=core,baseball_game,baseball_periods
ODDS_EVENT_MARKET_GROUPS=team_periods,mlb_player_props,mlb_alternate_props
```

## Grupos soportados

- `core`: `h2h`, `spreads`, `totals`.
- `baseball_game`: `alternate_spreads`, `alternate_totals`, `h2h_3_way`, `team_totals`, `alternate_team_totals`.
- `baseball_periods`: moneyline, 3-way, spreads, totals y alternativos para 1st inning, 1st 3, 1st 5 y 1st 7 innings.
- `team_periods`: team totals H1/H2/Q1/Q2/Q3/Q4 y alternativos. Algunos pueden no estar disponibles para MLB.
- `mlb_player_props`: batter/pitcher props principales.
- `mlb_alternate_props`: lineas alternativas de batter/pitcher props.
- `non_mlb`: `btts`, `draw_no_bet`; incluidos por compatibilidad, pero normalmente no aplican a MLB.

## Uso en codigo

`analysis.markets.analizar_mercados` agrega:

- `odds_event_id`: id del evento en The Odds API.
- `odds_loaded`: market keys cargados para el evento.
- `odds_markets`: todos los outcomes por market key.
- `odds_best`: mejor precio por outcome/linea/bookmaker.

El modelo actual sigue usando:

- `cuota_home`, `cuota_away`
- `cuota_rl_home`, `cuota_rl_away`
- `cuota_over`, `cuota_under`, `linea_total`

Los props y mercados por innings quedan disponibles para nuevos modelos sin
meterlos automaticamente al selector de picks hasta tener backtesting.
