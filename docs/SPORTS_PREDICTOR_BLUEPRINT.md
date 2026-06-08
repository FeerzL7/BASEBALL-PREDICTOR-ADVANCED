# Blueprint para SPORTS-PREDICTOR-ADVANCED

## Objetivo

Convertir el sistema actual, centrado en MLB, en una plataforma multi-deporte donde el core de apuestas sea comun y cada deporte implemente su propia ingestion, proyeccion, simulacion y settlement.

## Que debe convertirse en Core

- `BankrollLedger`: equivalente a `bankroll.tracker`.
- `StakingStrategy`: interfaz ya existe en `bankroll.staking`.
- `RiskManager`: equivalente a `utils.risk_management`.
- `OddsClient`: wrapper de The Odds API con sport configurable.
- `MarketNormalizer`: matching de eventos, mejores precios, no-vig, best odds.
- `ValueEngine`: EV, implied probability, no-vig, edge, Kelly, blending modelo/mercado.
- `Backtester`: cruce predicciones vs ledger, sensibilidad por umbral.
- `NotificationService`: Telegram/otros.
- `Logger`.
- `Artifacts`: CSV/JSON contracts para predicciones, ledger, snapshots y reportes.

## Que debe permanecer especifico de MLB

- Pitchers, bullpen, handedness, ERA, WHIP, K9, FIP.
- Lineup/bateadores, OPS, SLG, wRC+, plate appearances.
- Park factors y mapa equipo-estadio.
- Contexto de estadios cerrados/retractiles MLB.
- Proyeccion de carreras MLB.
- Settlement de ML/RL/TOTAL usando scores MLB.
- Grupos de mercados MLB props.

## Interfaces sugeridas

```python
class SportDataProvider:
    def get_events(date) -> list[Event]: ...
    def enrich_event(event) -> EventFeatures: ...
    def settle_bet(bet) -> Settlement: ...

class ProjectionModel:
    def project(event_features) -> Projection: ...

class ProbabilityModel:
    def probabilities(projection, market) -> dict: ...

class MarketAdapter:
    def supported_markets() -> list[str]: ...
    def normalize_odds(raw_event) -> NormalizedMarket: ...
    def select_main_lines(markets) -> dict: ...

class PickSelector:
    def evaluate(event, projection, odds) -> list[CandidatePick]: ...
```

## Entidades recomendadas

- `Event`: sport, league, date, home, away, venue, start_time, provider_ids.
- `TeamFeatures`: offense/defense/recent_form/injuries/context.
- `Projection`: expected_home, expected_away, expected_total, metadata.
- `MarketOdds`: market, selection, line, price, bookmaker.
- `CandidatePick`: market, selection, line, price, model_prob, market_prob, edge, ev, stake, reasons, data_quality_flags.
- `RiskDecision`: active/inactive, reason, final_stake.
- `BetLedgerEntry`.

## Patrones de diseno utiles

- Strategy: modelos de proyeccion por deporte, staking, risk rules.
- Adapter: proveedores de datos (`statsapi`, NBA API, football-data, etc.) y odds.
- Template Method/Pipeline: pasos comunes `load -> enrich -> project -> price -> value -> risk -> persist`.
- Repository: almacenamiento CSV/JSON ahora; futuro SQLite/Postgres.
- Factory/Registry: resolver deporte (`mlb`, `nba`, `nfl`, `nhl`, `soccer`) a sus adapters.
- DTO/dataclasses: reemplazar diccionarios mutables para contratos mas claros.

## Riesgos al migrar

- Acoplamiento por nombres de campos: `home_team`, `proj_home`, `valor_total`, etc. se repiten como strings.
- Formulas MLB no deben copiarse a deportes con scoring distinto.
- Mercado `spreads` no equivale a runline en todos los deportes.
- Poisson no siempre es adecuado; NBA/NFL pueden requerir normal/skellam/empirico/Monte Carlo.
- Settlement automatico depende de APIs confiables por deporte.
- Caches actuales no tienen versionado por temporada/deporte.
- Backtesting puede contaminar deportes si no incluye `sport/league`.
- The Odds API mercados avanzados varian mucho por deporte y plan.

## Ruta de migracion sugerida

1. Congelar contratos actuales: documentar columnas CSV y claves de partido.
2. Crear paquete `core/` con bankroll, odds base, value utilities, risk, logging.
3. Crear paquete `sports/mlb/` moviendo pitching/offense/projections/statcast/park/context MLB.
4. Introducir dataclasses o Pydantic ligero para `Event`, `Projection`, `Pick`.
5. Parametrizar `main.py` como `run_pipeline(sport="mlb")`.
6. Mantener compatibilidad CSV durante una fase.
7. Agregar tests de formulas EV/Kelly/no-vig/risk/ledger antes de cambiar modelos.
8. Migrar dashboard para filtrar por sport/league.

## Principio clave

El core no debe saber que es ERA, OPS, pitcher, park factor o bullpen. El core solo debe recibir probabilidades, cuotas, lineas, stakes, picks y resultados.
