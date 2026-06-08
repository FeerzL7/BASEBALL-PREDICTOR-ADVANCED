# Sistema de apuestas y bankroll

## Mercados soportados

- ML: moneyline ganador.
- RL: spread/runline con handicap publicado.
- TOTAL: Over/Under de carreras totales.

Los mercados avanzados de odds se almacenan (`odds_markets`, `odds_best`) pero no entran automaticamente al selector de picks.

## Stake

Hay dos fases:

1. `analysis.value` calcula stake preliminar por Kelly fraccionado si el mercado supera filtros.
2. `bankroll.staking.IntegerPercentStaking` reemplaza el stake activo por porcentaje entero conservador.

Reglas de `IntegerPercentStaking`:

- Si `mejor_pick` es `Ninguno`, stake 0.
- Si el stake preliminar del mercado es 0, stake 0.
- Parte de `MIN_STAKE_PCT`.
- TOTAL: +1 si EV >= 24 y prob >= 0.58; +1 adicional si EV >= 34, prob >= 0.60 y `mov_confirma`.
- ML: +1 si EV >= 10 y prob >= 0.55; +1 adicional si EV >= 16, prob >= 0.57 y `mov_confirma`.
- RL: +1 si EV >= 9 y prob >= 0.55; +1 adicional si EV >= 14, prob >= 0.57 y `mov_confirma`.
- Si hay `data_quality_flags`, reduce 1 pero no por debajo del minimo.
- Clamp final entre `MIN_STAKE_PCT` y `MAX_STAKE_PCT`.

Defaults en `bankroll.config`:

- `INITIAL_BANKROLL=1000`.
- `MIN_STAKE_PCT=1`.
- `MAX_STAKE_PCT=3`.
- `MAX_DAILY_EXPOSURE_PCT=6`.

## Gestion de riesgo

`utils.risk_management.aplicar_gestion_riesgo`:

- Limita picks activos por dia (`max_picks`, default inferido por parametros).
- Limita exposicion diaria total con `MAX_DAILY_EXPOSURE_PCT`.
- Limita stake por pick con `MAX_STAKE_PCT`.
- Desactiva picks contradichos por movimiento de linea.
- Ordena candidatos por valor/EV para asignar cupo.
- Mantiene diagnosticos ML/RL/TOTAL aunque cambie `mejor_pick` a `Ninguno`.

## Movimiento de linea

`data.line_movement` guarda snapshots diarios en `output/line_snapshots/YYYY-MM-DD.json` y compara primer snapshot vs ultimo.

Senales:

- `TOTAL_LINE_MOVE`: cambia la linea total; direccion `over` si sube, `under` si baja.
- `JUICE_SHIFT`: la linea no cambia pero se mueve el precio; interpreta direccion por abaratamiento/encarecimiento relativo.
- `ML_MOVE`: cuota se acorta o alarga mas de `UMBRAL_ML_MOVE=0.06`.

`ajustar_picks_por_movimiento` marca:

- `mov_confirma=True` si mercado se mueve a favor del pick.
- `mov_contradice=True` si se mueve en contra.

## Ledger de bankroll

Archivo fuente: `output/roi_tracking.csv`.

Campos:

```text
fecha, juego, mercado, seleccion, cuota, probabilidad, valor, resultado,
ganancia, stake_pct, stake_amount, bankroll_before, bankroll_after,
profit_amount, yield_pct, created_at, settled_at
```

Registro:

```text
stake_amount = bankroll_actual * stake_pct / 100
```

Profit:

```text
win:  unidades = cuota - 1; profit = stake_amount * unidades
lose: unidades = -1;        profit = -stake_amount
null: unidades = 0;         profit = 0
```

## Actualizacion de resultados

`tracking.roi_tracker.actualizar_resultados`:

- Lee pendientes.
- Usa `statsapi.schedule` por fecha para obtener scores.
- Resuelve ML/RL/TOTAL con `_resolver_resultado`.
- Liquida cada registro con `bankroll.tracker.liquidar_registro`.
- Reexporta reportes.

## ROI, yield, drawdown y metricas

`bankroll.tracker.metricas_acumuladas` calcula:

- Total resueltos.
- Wins, losses, pushes, pendientes.
- Stake total.
- Profit/ganancias.
- ROI:

```text
roi = profit / stake_total * 100
```

- Yield: en el codigo acumulado es igual a ROI.
- Hit rate:

```text
hit_rate = wins / resueltos * 100
```

- Growth:

```text
growth = (bankroll_actual - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100
```

- Equity curve y drawdown:

```text
high = max(high, bankroll_after)
drawdown = (bankroll_after - high) / high * 100
max_drawdown_pct = minimo drawdown observado
```

## Reportes exportados

- `output/bankroll_history.csv`: curva de bankroll y drawdown por pick resuelto.
- `output/bankroll_monthly_stats.csv`: picks, wins/losses/pushes, stake, profit, ROI/yield, hit rate, bankroll inicial/final, growth, max drawdown, cuota media.
- `dashboard/roi_dashboard.py`: Streamlit para ROI, hit rate, ganancia, cuota media, EV, racha, curva bankroll, rendimiento por mercado/cuota y picks recientes.

## Backtesting

`backtesting/backtesting.py`:

- Lee `output/predicciones_*.csv`.
- Cruza picks con `output/roi_tracking.csv`.
- Calcula stats globales, por mercado y por bandas de EV `[0,3,5,7,10,15,20,30]`.
- Sugiere umbrales con ROI maximo y minimo de picks.
- Puede modificar `analysis/value.py` con `--calibrar`; esto es una capacidad existente, no se ejecuto aqui.
