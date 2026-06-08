# Inventario total del repositorio

Proyecto: `BASEBALL-PREDICTOR-ADVANCED`. Evidencia usada: arbol de archivos, imports, definiciones AST y lectura de modulos Python/Markdown. No se modifico codigo fuente.

## Arbol de directorios

```text
.
|-- .env
|-- .gitignore
|-- ANALISIS_FODA.md
|-- ODDS_MARKETS.md
|-- README.md
|-- main.py
|-- analysis/
|   |-- bullpen.py
|   |-- context.py
|   |-- defense.py
|   |-- ensemble.py
|   |-- h2h.py
|   |-- markets.py
|   |-- offense.py
|   |-- park_factors.py
|   |-- pitching.py
|   |-- projections.py
|   |-- simulation.py
|   |-- statcast.py
|   `-- value.py
|-- backtesting/
|   |-- init.py
|   `-- backtesting.py
|-- bankroll/
|   |-- __init__.py
|   |-- config.py
|   |-- staking.py
|   `-- tracker.py
|-- dashboard/
|   `-- roi_dashboard.py
|-- data/
|   |-- line_movement.py
|   |-- odds_api.py
|   `-- odds_markets.py
|-- logs/
|   `-- mlb_YYYY-MM-DD.log
|-- notifications/
|   `-- telegram.py
|-- output/
|   |-- adv_batting_cache.json
|   |-- adv_pitching_cache.json
|   |-- offense_cache.json
|   |-- bankroll_history.csv
|   |-- bankroll_monthly_stats.csv
|   |-- backtest_results*.csv
|   |-- predicciones_YYYY-MM-DD.csv
|   |-- roi_tracking.csv
|   `-- line_snapshots/YYYY-MM-DD.json
|-- predicciones/
|   `-- predicciones_2025-07-02.csv
|-- tracking/
|   `-- roi_tracker.py
`-- utils/
    |-- constants.py
    |-- logger.py
    |-- mlb_api.py
    |-- poisson_math.py
    `-- risk_management.py
```

Nota: existen carpetas `__pycache__` con bytecode `.pyc`; son artefactos generados por Python y no contienen logica fuente nueva.

## Componentes por directorio

### Raiz

- `main.py` - Orquestador principal. Importancia: critica. Ejecuta el pipeline diario: logger, stats avanzadas, pitchers, ofensiva, defensa, H2H, contexto, proyecciones, simulaciones, odds, movimiento de linea, valor, staking, riesgo, tracking ROI, export CSV y Telegram.
- `README.md` - Documentacion historica del sistema. Importancia: media. Describe flujo general y requisitos, aunque parte del texto aparece con mojibake.
- `ODDS_MARKETS.md` - Guia de configuracion de mercados de The Odds API. Importancia: alta para datos/odds. Explica grupos `core`, innings, props y uso de mercados avanzados por evento.
- `ANALISIS_FODA.md` - Documento de analisis estrategico. Importancia: media; evidencia de decisiones de producto/negocio.
- `.env` - Configuracion local con secretos/variables. Importancia: critica operacional. No debe migrarse como secreto plano.
- `.gitignore` - Configuracion Git minima. Importancia: baja.

### `analysis/`

- `pitching.py` - Extrae schedule y abridores desde `statsapi`; calcula ERA/WHIP/K9 temporada, salidas recientes y `ERA_efectiva = 0.60 * ERA_temporada + 0.40 * ERA_reciente`. Filtra TBD. Importancia: critica.
- `bullpen.py` - Calcula ERA/WHIP de relevistas ponderado por innings; excluye starters por ratio `gamesStarted/gamesPlayed >= 0.30`; cachea en memoria. Importancia: alta.
- `offense.py` - Estima ofensiva por equipo vs mano del pitcher: top 5 bateadores por PA, splits vs R/L, OPS ponderado, carreras recientes, wRC+ aproximado y cache en disco. Importancia: critica.
- `defense.py` - Agrega errores, doble plays y fielding percentage por equipo. Importancia: media; no se observa uso fuerte posterior en proyeccion actual.
- `h2h.py` - Calcula historial reciente entre equipos con carreras promedio y win rate. Importancia: media; disponible, pero H2H en proyeccion esta apagado por default.
- `context.py` - Obtiene clima desde Open-Meteo por coordenadas de estadio y hora local por timezone. Importancia: alta como capa contextual; ajustes climaticos estan apagados por default en proyeccion.
- `park_factors.py` - Calcula park factors dinamicos con stats casa/visitante de MLB y cache 24h; fallback a historicos. Importancia: critica para totales.
- `statcast.py` - Stats avanzadas aproximadas: FIP, OPS, SLG, wRC+ proxy, K%, BB%, HardHit proxy; caches JSON. Importancia: critica para proyecciones.
- `projections.py` - Motor de carreras esperadas. Combina forma ofensiva, pitcheo rival, bullpen, FIP, lineup, park factor y, opcionalmente, contexto/H2H. Importancia: critica.
- `simulation.py` - Simulaciones Poisson para ML y runline; ensemble opcional apagado por default. Importancia: critica.
- `ensemble.py` - Capa opcional de regresion lineal sobre carreras recientes y peso adaptativo por coeficiente de variacion. Importancia: media/experimental; `ENABLE_ENSEMBLE=False`.
- `markets.py` - Matching fuzzy de eventos y extraccion de mejores cuotas ML/RL/totales; normaliza todos los mercados avanzados. Importancia: critica para conectar modelo con mercado.
- `value.py` - Selector de picks. Calcula probabilidades no-vig, mezcla modelo/mercado, edge, EV, Kelly fraccionado, filtros por mercado y mejor pick. Importancia: critica.

### `data/`

- `odds_markets.py` - Catalogo de mercados The Odds API y helpers para expandir grupos, separar featured/event y chunking. Importancia: alta.
- `odds_api.py` - Cliente The Odds API (`/sports/{sport}/odds` y opcional `/events/{eventId}/odds`). Maneja API key, errores 401/403 y merge de mercados event-level. Importancia: critica.
- `line_movement.py` - Persistencia de snapshots intradia y deteccion de movimiento: total line move, juice shift y ML move. Importancia: alta para confianza/riesgo.

### `bankroll/`

- `config.py` - Constantes de bankroll desde environment: archivos CSV, bankroll inicial, stake min/max y exposicion diaria. Importancia: alta.
- `staking.py` - Estrategia modular de stake entero por porcentaje. Ajusta stake por EV/probabilidad/movimiento y penaliza flags de calidad. Importancia: alta.
- `tracker.py` - Ledger de apuestas con bankroll before/after, stake amount, profit, yield, equity curve, drawdown y stats mensuales. Importancia: critica.
- `__init__.py` - Inicializador vacio. Importancia: baja.

### `tracking/`

- `roi_tracker.py` - Fachada historica compatible con `main.py`; delega en `bankroll.tracker`, registra picks y resuelve resultados pendientes con `statsapi.schedule`. Importancia: critica.

### `backtesting/`

- `backtesting.py` - Lee predicciones historicas y ROI resuelto; cruza picks, calcula sensibilidad por EV, sugiere umbrales y opcionalmente reescribe `analysis/value.py`. Importancia: alta para calibracion, aunque `--calibrar` modifica codigo.
- `init.py` - Archivo vacio/no operativo. Importancia: baja.

### `dashboard/`

- `roi_dashboard.py` - App Streamlit con metricas, filtros, curva bankroll, hit rate por mercado, distribucion EV, rendimiento por cuota y tablas. Importancia: media/alta para monitoreo.

### `notifications/`

- `telegram.py` - Formatea y envia picks con stake y resumen ROI a Telegram si hay `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`. Importancia: media operacional.

### `utils/`

- `constants.py` - Carga `.env` simple, API key, sport/region/markets/bookmakers, grupos de odds, `TODAY` y park factors historicos. Importancia: critica.
- `logger.py` - Logger raiz con consola coloreada y archivo rotado diario `logs/mlb_YYYY-MM-DD.log`. Importancia: alta.
- `poisson_math.py` - PMF/CDF/SF Poisson sin SciPy. Importancia: alta, usado por simulacion/value.
- `risk_management.py` - Limita picks activos por exposicion diaria, max stake, max picks, contradiccion de linea y duplicados de mercado. Importancia: alta.
- `mlb_api.py` - Helper legado para stats vs mano del pitcher. Importancia: baja/media; no aparece en `main.py`.

## Archivos de datos y artefactos

- `output/predicciones_YYYY-MM-DD.csv` - CSV final diario con columnas clave: equipos, pitchers, proyecciones, probabilidades, linea total, picks ML/RL/TOTAL, EV, stake, riesgo, odds, Kelly y contexto de parque.
- `predicciones/predicciones_2025-07-02.csv` - Prediccion historica fuera de `output`; parece artefacto previo.
- `output/roi_tracking.csv` - Ledger principal de picks. Columnas normalizadas: fecha, juego, mercado, seleccion, cuota, probabilidad, valor, resultado, ganancia, stake_pct, stake_amount, bankroll_before, bankroll_after, profit_amount, yield_pct, created_at, settled_at.
- `output/bankroll_history.csv` - Equity curve con drawdown.
- `output/bankroll_monthly_stats.csv` - Resumen mensual: picks, wins/losses/pushes, stake, profit, ROI/yield, hit rate, bankroll, growth, max drawdown, average odds.
- `output/backtest_results*.csv` - Resultados de backtesting: detalle, resumen y sensibilidad.
- `output/*cache.json` - Caches de stats avanzadas/ofensiva/parques. Reducen llamadas API.
- `output/line_snapshots/*.json` - Snapshots intradia de cuotas The Odds API para detectar movimiento.
- `logs/mlb_YYYY-MM-DD.log` - Logs rotados por fecha.

## Dependencias externas

- Python stdlib: `argparse`, `csv`, `glob`, `json`, `logging`, `math`, `os`, `re`, `sys`, `datetime`, `collections.defaultdict`, `dataclasses`, `typing`, `itertools.groupby`.
- Paquetes: `statsapi`, `requests`, `pandas`, `pytz`, `streamlit`, `plotly`.
- Servicios/API: MLB Stats API via `statsapi`; The Odds API v4; Open-Meteo; Telegram Bot API.

## Dependencias internas principales

- `main.py` depende de casi todos los modulos de `analysis`, `data`, `tracking`, `bankroll`, `utils` y `notifications`.
- `analysis.projections` depende de `analysis.park_factors`, `analysis.statcast`, `utils.logger`.
- `analysis.value` depende de `utils.poisson_math` y `utils.logger`.
- `analysis.simulation` depende de `utils.poisson_math`; puede importar `analysis.ensemble` si se activa.
- `data.odds_api` depende de `data.odds_markets` y `utils.constants`.
- `tracking.roi_tracker` depende de `bankroll.tracker`.
- `utils.risk_management` y `bankroll.staking` dependen de `bankroll.config`.

## Importancia por capa

- Critica: `main.py`, `analysis/pitching.py`, `analysis/offense.py`, `analysis/projections.py`, `analysis/simulation.py`, `analysis/value.py`, `analysis/markets.py`, `data/odds_api.py`, `bankroll/tracker.py`, `tracking/roi_tracker.py`, `utils/constants.py`.
- Alta: `analysis/bullpen.py`, `analysis/context.py`, `analysis/park_factors.py`, `analysis/statcast.py`, `data/line_movement.py`, `data/odds_markets.py`, `bankroll/staking.py`, `utils/risk_management.py`, `utils/logger.py`, `utils/poisson_math.py`, `backtesting/backtesting.py`.
- Media: `analysis/defense.py`, `analysis/h2h.py`, `analysis/ensemble.py`, `dashboard/roi_dashboard.py`, `notifications/telegram.py`, `ANALISIS_FODA.md`, `ODDS_MARKETS.md`.
- Baja: `__init__.py`, bytecode `__pycache__`, `.gitignore`.
