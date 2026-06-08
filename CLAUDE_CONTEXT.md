# Contexto para Claude: BASEBALL-PREDICTOR-ADVANCED

## Resumen ejecutivo

Este repositorio es un pipeline diario de prediccion y apuestas MLB. No es solo un modelo deportivo: es un sistema completo de valor esperado, bankroll, riesgo, tracking, backtesting, dashboard y notificaciones.

La unidad de trabajo es una lista de diccionarios `partidos`. `main.py` va enriqueciendo cada partido: schedule/pitchers, ofensiva, defensa, H2H, clima, proyecciones de carreras, simulaciones Poisson, odds, movimiento de linea, EV, stake, riesgo, tracking y CSV final.

El objetivo real del sistema es encontrar apuestas con valor, no adivinar ganadores. Primero proyecta carreras, luego calcula probabilidades, despues compara contra mercado no-vig y solo activa picks si pasan filtros.

## Pipeline principal

1. Configura logger.
2. Carga stats avanzadas (`analysis.statcast`).
3. Obtiene schedule y abridores (`analysis.pitching`), excluyendo TBD.
4. Agrega ofensiva (`analysis.offense`).
5. Agrega defensa (`analysis.defense`).
6. Agrega H2H (`analysis.h2h`).
7. Agrega contexto ambiental (`analysis.context`).
8. Proyecta carreras (`analysis.projections`).
9. Simula ML/RL con Poisson (`analysis.simulation`).
10. Obtiene odds (`data.odds_api`).
11. Guarda snapshot de lineas (`data.line_movement`).
12. Une odds con partidos (`analysis.markets`).
13. Calcula EV y picks (`analysis.value`).
14. Ajusta por movimiento de linea.
15. Aplica staking dinamico (`bankroll.staking`).
16. Aplica gestion de riesgo (`utils.risk_management`).
17. Actualiza resultados pendientes y registra picks (`tracking.roi_tracker`).
18. Exporta `output/predicciones_YYYY-MM-DD.csv`.
19. Envia Telegram si esta configurado.

## Filosofia del sistema

- Modelo primero estima carreras esperadas.
- Poisson convierte medias de carreras en probabilidades.
- El mercado se usa como ancla: se calcula probabilidad implicita sin vig y se mezcla con el modelo.
- EV, edge, probabilidad minima, rango de cuota y calidad de datos filtran picks.
- Kelly existe, pero fraccionado y con techo.
- Staking final es entero y conservador.
- Riesgo puede apagar picks aunque el modelo vea valor.
- Tracking financiero es fuente de verdad de rendimiento.

## Formulas esenciales

ERA efectiva:

```text
ERA_efectiva = 0.60 * ERA_temporada + 0.40 * ERA_reciente
```

ERA rival combinada:

```text
ERA_combinada = 0.67 * ERA_abridor + 0.33 * ERA_bullpen
```

Proyeccion de carreras:

```text
proj = max(base_runs * f_pitcheo * f_lineup * park_factor, 2.0)
```

EV:

```text
EV_pct = (prob * cuota - 1) * 100
```

No-vig:

```text
pa = (1/cuota_a) / ((1/cuota_a) + (1/cuota_b))
```

Blending:

```text
prob_adj = model_prob * model_weight + market_prob * (1 - model_weight)
```

Kelly fraccionado:

```text
b = cuota - 1
kelly_full = (prob * (b + 1) - 1) / b
stake_pct = min(kelly_full * 0.18 * 100, 1.25)
```

## Componentes criticos

- `main.py`: orquestador.
- `analysis/projections.py`: convierte features MLB en carreras esperadas.
- `analysis/value.py`: decision economica por ML/RL/TOTAL.
- `analysis/markets.py`: matching y mejores cuotas.
- `data/odds_api.py`: The Odds API.
- `bankroll/tracker.py`: ledger real.
- `tracking/roi_tracker.py`: registro/settlement compatible con main.
- `utils/risk_management.py`: activacion final.

## Reglas arquitectonicas

- No copiar formulas MLB a otros deportes sin recalibracion.
- Separar core de deporte: bankroll, odds, EV, risk y backtesting son core; pitching/offense/park factors son MLB.
- Mantener CSV de predicciones como contrato hasta reemplazarlo formalmente.
- No asumir que Poisson aplica a todos los deportes.
- No usar H2H/contexto como si estuvieran activos: en proyeccion actual estan apagados por flags.
- No eliminar defaults/fallbacks sin reemplazo; sostienen la operacion diaria.
- No registrar picks sin stake final y sin pasar riesgo.

## Convenciones actuales

- Diccionarios mutables en vez de clases de dominio.
- Campos por mercado: `pick_ml`, `valor_ml`, `stake_pct_ml`, `edge_ml`; igual para RL/TOTAL.
- `mejor_pick` usa strings como `ML: Team`, `RL: Team`, `TOTAL: Over`.
- Resultado de apuestas: `win`, `lose`, `null`, `pendiente`.
- Archivos en `output/` son estado operativo.
- Logs diarios en `logs/mlb_YYYY-MM-DD.log`.

## Restricciones importantes

- `.env` puede contener secretos. No migrar ni exponer API keys.
- `backtesting.py --calibrar` modifica `analysis/value.py`; usar con cuidado.
- The Odds API event markets pueden fallar 401/403 segun plan; el sistema conserva core markets.
- `README.md` tiene texto con mojibake; confiar en codigo para detalles.
- `__pycache__` no importa.

## Lecciones aprendidas codificadas

- Contexto ambiental debe correr antes de proyecciones para que pueda afectar park factor si se activa.
- Runline debe usar probabilidad real de cubrir handicap, no probabilidad ML.
- Oracle Park fue corregido como abierto, no retractil.
- Totales parecen tener prioridad estructural y umbrales mas exigentes.
- ML/RL se mantienen activos (`ENABLE_ML_PICKS=True`, `ENABLE_RL_PICKS=True`), aunque comentarios indican que alguna vez fueron diagnosticos por ROI negativo.

## Errores que deben evitarse

- Confundir `prob_home_win` con `rl_home_prob`.
- Usar cuotas con vig como probabilidad de mercado sin normalizar.
- Activar picks con `data_quality_flags` criticos.
- Ignorar movimiento de linea contradictorio.
- Mezclar predicciones de fechas/deportes en el mismo ledger sin columna `sport`.
- Romper columnas esperadas por dashboard/backtesting.

## Para migrar a SPORTS-PREDICTOR-ADVANCED

Extraer a core:

- Odds client.
- Market normalization.
- EV/no-vig/Kelly/blending.
- Bankroll ledger.
- Staking.
- Risk.
- Backtesting.
- Dashboard base.
- Telegram.

Mantener como MLB plugin:

- Pitching.
- Bullpen.
- Offense.
- Statcast proxies.
- Park factors.
- MLB context/venues.
- MLB projections.
- MLB settlement.

La frase guia: el core no debe saber que existe un pitcher; solo debe saber que una seleccion tiene una probabilidad, una cuota, una linea, un EV, un stake y un resultado.
