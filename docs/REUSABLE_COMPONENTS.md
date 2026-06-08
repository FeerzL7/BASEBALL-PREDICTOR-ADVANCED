# Componentes reutilizables

Clasificacion:

1. Totalmente reutilizable.
2. Reutilizable con adaptacion.
3. Exclusivo de MLB.

## Totalmente reutilizable

- `utils.poisson_math` - Matematica Poisson generica. Util para deportes con conteos discretos; en deportes de alta puntuacion puede requerir otra distribucion, pero el componente en si es generico.
- `utils.logger` - Logging de consola/archivo. No depende de MLB.
- `bankroll.config` - Rutas y limites por environment. Generico.
- `bankroll.tracker` - Ledger, ROI, yield, bankroll, drawdown y stats mensuales. Generico para apuestas.
- `bankroll.staking` - Estrategia por porcentaje entero. Generica si los partidos conservan campos `mejor_pick`, `valor_*`, `prob_*`, `stake_pct_*`.
- `utils.risk_management` - Gestion de exposicion diaria, max picks, contradiccion de linea. Reutilizable si se estandariza el contrato de picks.
- `data.odds_api` - Cliente The Odds API parcialmente generico; requiere parametrizar `SPORT` y mercados.
- `data.odds_markets` - Estructura de grupos parcialmente reusable; `core` es universal, grupos MLB deben separarse.
- `dashboard.roi_dashboard` - Dashboard de ROI generico con pequenos cambios de branding.
- `notifications.telegram` - Notificaciones genericas; solo texto/branding y parse de pick deben adaptarse.
- `backtesting.backtesting` - Metodologia generica de cruzar predicciones vs ledger y analizar EV; depende de columnas que pueden estandarizarse.

## Reutilizable con adaptacion

- `analysis.value` - La filosofia EV/no-vig/Kelly/blending es reusable. Adaptar mercados, probabilidades, umbrales, caps y formulas de handicap/totales por deporte.
- `analysis.simulation` - Reusable para deportes de baja anotacion o conteos independientes; adaptar max score y distribucion para NBA/NFL/NHL/soccer.
- `analysis.markets` - Matching y extraccion de mejores cuotas reutilizables; adaptar nomenclatura de equipos, mercados y seleccion de linea principal.
- `data.line_movement` - Reusable para ML/totals/spreads, pero debe generalizar nombres (`home_rl`, `away_rl`, lineas, periodos).
- `analysis.ensemble` - Reusable como capa de tendencia sobre series recientes de scoring; adaptar fuente y significado de `runs`.
- `analysis.context` - Reusable si el deporte tiene venue/weather relevante; adaptar estadios, coordenadas, timezones y si indoor/outdoor importa.
- `tracking.roi_tracker` - La fachada de registro es reusable; la resolucion automatica por scores depende de API/deporte.
- `main.py` - El pipeline como patron es reusable, pero su implementacion esta acoplada a MLB.

## Exclusivo de MLB

- `analysis.pitching` - Depende de pitchers probables, ERA, WHIP, K9, pitcher hand, gameLog de salidas. Excluyente de baseball.
- `analysis.bullpen` - Concepto bullpen/relievers/starters es MLB.
- `analysis.offense` - Splits vs RHP/LHP, top bateadores, plate appearances, OPS, wRC+ proxy son MLB.
- `analysis.park_factors` - Estadios MLB, formula home/away baseball y park factor de carreras.
- `analysis.statcast` - FIP, SLG, OPS, K%, BB%, HardHit proxy son baseball.
- `analysis.projections` - Formula actual de carreras incorpora ERA/FIP/OPS/wRC+/park factor MLB.
- `analysis.defense` - Errores, double plays, fielding percentage son baseball.
- `analysis.h2h` - El H2H como concepto es generico, pero la implementacion con `statsapi` MLB es exclusiva.
- `utils.constants.PARK_FACTORS` - Tabla de estadios MLB.
- `utils.mlb_api` - Helper MLB.

## Recomendacion de extraccion

Core generico:

- odds client + market normalization.
- probability/value engine interfaces.
- bankroll ledger.
- staking/risk.
- logging.
- backtesting.
- dashboard/notifications.

Sports-specific plugins:

- data provider.
- projection model.
- market definitions.
- settlement resolver.
- context provider.
- naming/team mapping.
