# Motor de prediccion

## Entrada primaria

El motor parte de partidos MLB del dia via `statsapi.schedule()`. Para cada partido requiere equipos, pitchers probables, estadio y hora. Si un pitcher esta TBD, `main.py` excluye el partido antes del pipeline estadistico.

## Proyeccion de carreras

Formula central en `analysis.projections.proyectar_carreras`:

```text
base = max(runs_last_5, 2.0)
f_pit = clamp((ERA_combinada / ERA_LIGA) * 0.55 + (FIP / FIP_LIGA) * 0.45)
f_lin = clamp((OPS / OPS_LIGA + wRC_plus / WRC_PLUS_LIGA) / 2)
proyeccion = max(base * f_pit * f_lin * park_factor, 2.0)
```

Donde:

```text
ERA_combinada = ERA_abridor * 0.67 + ERA_bullpen * 0.33
```

El abridor trae `ERA_efectiva` desde `analysis.pitching`:

```text
ERA_efectiva = ERA_temporada * 0.60 + ERA_reciente * 0.40
```

Si no hay recientes, usa 100% ERA de temporada.

## Factores de ponderacion y clamps

- `PESO_BULLPEN = 0.33`, `PESO_ABRIDOR = 0.67`.
- `_F_MIN = 0.60`, `_F_MAX = 1.55`.
- Piso de carreras por equipo: `2.0`.
- FIP liga: `4.10`; ERA liga: `4.20`; OPS liga: `0.730`; wRC+ liga: `100`.
- FIP aproximado:

```text
FIP = (13*HR + 3*(BB+HBP) - 2*K) / IP + 3.10
```

con clamps entre 1.5 y 8.0 y fallback a 4.10 si IP < 10.

## Park factors

`analysis.park_factors` calcula:

```text
PF_raw = (runs_home_total / games_home) / (runs_away_total / games_away)
PF_suavizado = 0.80 * PF_raw + 0.20 * 1.0
```

Si no hay suficientes datos (`_MIN_JUEGOS=15`) usa historicos de `utils.constants.PARK_FACTORS`.

`analysis.projections.ajustar_park_factor` puede aplicar temperatura, viento y noche, pero `USE_CONTEXT_ADJUSTMENTS=False`, asi que actualmente devuelve el park factor base con minimo 0.85 salvo que se active.

## Ofensiva

`analysis.offense` calcula:

- Top `N_BATEADORES=5` por plate appearances.
- Splits individuales vs RHP/LHP si existen.
- OPS ponderado por PA.
- `wRC+` aproximado:

```text
wRC+ ~= max(50, min((OPS / 0.730) * 100, 175))
```

- Carreras recientes de los ultimos `N_JUEGOS_RECIENTES=10` juegos.

## Probabilidades Poisson

PMF propia en `utils.poisson_math`:

```text
P(X=k) = exp(k*log(mu) - mu - lgamma(k+1))
```

ML:

```text
prob_home = sum(P(H=h)*P(A=a) para h>a)
prob_away = sum(P(H=h)*P(A=a) para a>h)
normalizar por prob_home + prob_away
```

Runline:

```text
P(cubrir) = sum(P(T=t)*P(O=o) para t + handicap > o)
```

Total:

```text
Over:  P(X > linea) = sf(linea, mu_total)
Under: P(X < linea) = cdf(linea - 1, mu_total)
```

## Generacion de picks

`analysis.value.analizar_valor` ejecuta:

1. Recalcula probabilidades ML desde `proj_home/proj_away`.
2. Evalua ML con `_decidir_ml`.
3. Evalua RL con `_decidir_rl`, recalculando probabilidad con handicap real de mercado.
4. Evalua TOTAL con `_decidir_total`.
5. Guarda predicciones trazables.
6. Selecciona `mejor_pick` con `_mejor_pick`.

## Probabilidad de mercado y edge

Para dos cuotas decimales:

```text
implied_a = 1 / cuota_a
implied_b = 1 / cuota_b
no_vig_a = implied_a / (implied_a + implied_b)
no_vig_b = implied_b / (implied_a + implied_b)
edge = model_prob_raw - no_vig_prob
```

Mezcla modelo/mercado:

```text
prob_adj = model_prob * model_weight + market_prob * (1 - model_weight)
prob_adj = clamp(prob_adj, 0.02, cap)
```

Pesos/caps:

- ML: `PROB_MODEL_WEIGHT_ML=0.35`, `PROB_CAP_ML=0.58`.
- RL: `PROB_MODEL_WEIGHT_RL=0.35`, `PROB_CAP_RL=0.57`.
- TOTAL: `PROB_MODEL_WEIGHT_TOTAL=0.62`, `PROB_CAP_TOTAL=0.62`.

## EV y Kelly

EV:

```text
EV_pct = (probabilidad * cuota - 1) * 100
```

Kelly fraccionado:

```text
b = cuota - 1
kelly_full = (prob * (b + 1) - 1) / b
stake_pct = min(kelly_full * 0.18 * 100, 1.25)
```

Si Kelly full <= 0, stake = 0.

## Umbrales por mercado

ML:

- EV >= 6.
- Prob >= 0.535.
- Cuota entre 1.88 y 2.12.
- Edge entre 0.035 y 0.180.

RL:

- EV >= 5.
- Prob >= 0.53.
- Cuota entre 1.88 y 2.12.
- Edge entre 0.030 y 0.160.

TOTAL:

- EV >= 15.
- Prob >= 0.56.
- Diferencia proyeccion-linea >= 1.00.
- Cuota entre 1.75 y 2.20.
- Sin bloqueo por calidad de datos.

## Rankings y seleccion final

`_mejor_pick` arma candidatos solo con stake > 0 y filtros cumplidos. ML/RL tienen prioridad 1; TOTAL prioridad 2. El ganador se elige por `(prioridad, EV)`. Por eso TOTAL gana estructuralmente si cumple, incluso contra ML/RL con EV comparable.

## Calidad de datos

Flags detectados:

- `home_pitcher_fallback`, `away_pitcher_fallback`.
- `home_offense_fallback`, `away_offense_fallback`.
- `home_runs_recent_missing`, `away_runs_recent_missing`.

El pick se bloquea si hay dos fallbacks de pitcher o dos fallbacks de ofensiva.

## Ensemble opcional

`analysis.ensemble` puede combinar Poisson con regresion lineal de carreras recientes. La mezcla usa un alpha adaptativo segun coeficiente de variacion: equipos consistentes conservan mas peso Poisson; equipos muy variables reducen alpha. Esta capa no corre con la configuracion actual porque `ENABLE_ENSEMBLE=False`.
