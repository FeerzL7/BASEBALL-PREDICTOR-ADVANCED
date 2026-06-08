# Fuentes de datos

## MLB Stats API via `statsapi`

Usos detectados:

- `statsapi.schedule`:
  - `analysis.pitching.analizar_pitchers`: schedule del dia, pitchers probables, equipos, hora, venue.
  - `analysis.offense._runs_recientes`: juegos ultimos 30 dias por equipo.
  - `tracking.roi_tracker.actualizar_resultados`: scores para resolver picks.
- `statsapi.lookup_player`:
  - `analysis.pitching.get_pitcher_stats`: resolver pitcher por nombre.
- `statsapi.player_stat_data`:
  - `analysis.pitching._stats_temporada`: stats temporada pitching.
  - `analysis.pitching._stats_recientes`: gameLog de salidas recientes.
- `statsapi.lookup_team`:
  - `analysis.bullpen`, `analysis.offense`, `analysis.defense`, `analysis.h2h`, `analysis.statcast`, `utils.mlb_api`.
- `statsapi.get` endpoints:
  - `people`: mano del pitcher.
  - `stats`: top bateadores, pitchers por equipo.
  - `person` con hydrate `statSplits`: splits de bateadores vs R/L.
  - `team_stats`: hitting/pitching temporada y splits.
  - `teams_stats`: park factors por home/away.
  - `teams`: lista de equipos MLB para cargar stats avanzadas.

## The Odds API

Archivo: `data/odds_api.py`.

Base URL:

```text
https://api.the-odds-api.com/v4
```

Endpoints:

- Featured/core:

```text
/sports/{SPORT}/odds
```

- Event-level avanzado:

```text
/sports/{SPORT}/events/{eventId}/odds
```

Parametros:

- `regions` o `bookmakers`.
- `markets`.
- `oddsFormat=decimal`.
- `apiKey`.

Configuracion desde `utils.constants`:

- `API_KEY` o `ODDS_API_KEY`.
- `SPORT`, default `baseball_mlb`.
- `REGION`, default `us`.
- `MARKETS`, default historico.
- `ODDS_MARKET_GROUPS`.
- `ODDS_EVENT_MARKET_GROUPS`.
- `ODDS_FETCH_EVENT_MARKETS`.
- `ODDS_BOOKMAKERS`.

Mercados core:

- `h2h`.
- `spreads`.
- `totals`.

Mercados avanzados documentados:

- Alternativos de juego, innings, team totals, batter props, pitcher props y alternativos.

## Open-Meteo

Archivo: `analysis/context.py`.

Endpoint:

```text
https://api.open-meteo.com/v1/forecast
```

Parametros:

- `latitude`, `longitude`.
- `current_weather=true`.
- `timezone=UTC`.
- Si hay hora de juego: `hourly=temperature_2m,windspeed_10m,weathercode`, `start_date`, `end_date`.

Salida normalizada:

- `temperatura`.
- `viento_kph`.
- `condiciones`.
- `fuente`: `open-meteo-hourly`, `open-meteo-current` o `default`.
- `is_default`.
- `venue_default` agregado por `analizar_contexto`.

## Telegram Bot API

Archivo: `notifications/telegram.py`.

Uso:

- Envia picks con stake y resumen ROI.
- Requiere `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`.
- Si falta configuracion, omite notificacion y retorna `False`.

## Archivos locales

### Configuracion

- `.env`: leido manualmente por `utils.constants._env`; tambien `bankroll.config` usa `os.getenv`.
- `ODDS_MARKETS.md`: documentacion de grupos disponibles.

### Caches

- `output/offense_cache.json`: ofensiva por equipo/mano, TTL 6h.
- `output/adv_pitching_cache.json`: stats avanzadas pitching, TTL 24h.
- `output/adv_batting_cache.json`: stats avanzadas batting, TTL 24h.
- `output/park_factors_cache.json`: generado si existe ejecucion de park factors, TTL 24h.

### Snapshots

- `output/line_snapshots/YYYY-MM-DD.json`: lista de snapshots con timestamp y eventos normalizados.

### Predicciones y tracking

- `output/predicciones_YYYY-MM-DD.csv`.
- `predicciones/predicciones_2025-07-02.csv`.
- `output/roi_tracking.csv`.
- `output/bankroll_history.csv`.
- `output/bankroll_monthly_stats.csv`.
- `output/backtest_results.csv`, `_resumen.csv`, `_sensibilidad.csv`.

### Logs

- `logs/mlb_YYYY-MM-DD.log`: rotacion diaria configurada por `utils.logger`.

## Transformaciones de datos

- Team/event matching: normalizacion sin acentos y fuzzy score > 0.6.
- Odds: mejores precios por outcome; totals elige linea con pares over/under y menor vig respecto a consenso; spreads prefiere handicap cercano a 1.5 y mejor precio.
- MLB stats: clamps y defaults para evitar valores corruptos/extremos.
- Park factors: suavizado 80/20 hacia neutral.
- Probabilidades: no-vig y blending modelo/mercado.
- Ledger: normalizacion de tipos CSV a floats/ints y migracion de registros antiguos a columnas nuevas.
