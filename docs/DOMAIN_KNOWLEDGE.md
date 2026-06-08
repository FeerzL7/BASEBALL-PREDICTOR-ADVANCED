# Conocimiento de dominio

## Como piensa el sistema

El sistema no intenta predecir un marcador exacto como objetivo final. Primero estima medias de carreras esperadas por equipo (`proj_home`, `proj_away`), luego convierte esas medias en probabilidades por mercado con Poisson, y finalmente compara esas probabilidades contra el precio del mercado. La apuesta solo existe si la diferencia modelo-mercado supera filtros de EV, probabilidad, cuota, edge, calidad de datos, movimiento de linea y exposicion.

Inferencia basada en codigo: el sistema esta disenado como buscador de valor esperado, no como pronosticador narrativo. Evidencia: `analysis.value` mezcla probabilidad del modelo con probabilidad no-vig de mercado antes de calcular EV, y `utils.risk_management` puede desactivar picks aunque exista una prediccion.

## Filosofia de prediccion

- La variable base es carreras esperadas, no win/loss directo.
- El pitcheo rival importa por abridor y bullpen. El abridor usa ERA temporada y forma reciente; bullpen usa ERA/WHIP ponderado por IP de relevistas.
- La ofensiva se aproxima por el corazon del lineup: top 5 bateadores por PA, con splits vs mano del pitcher cuando se pueden obtener.
- El estadio importa por park factor dinamico/historico.
- Los datos avanzados se aproximan con MLB API: FIP, wRC+ proxy, OPS, SLG, K%, BB%.
- H2H y clima existen, pero estan apagados por default en la proyeccion actual para evitar ruido por muestras pequenas o defaults de APIs.

## Filosofia de apuestas

- Se evalua ML, RL y TOTAL por separado porque cada mercado responde a una dinamica distinta.
- ML/RL usan diferencia entre equipos y edge contra mercado.
- TOTAL usa suma de carreras proyectadas contra linea (`proj_total - linea_total`) y requiere diferencia minima de 1 carrera.
- El mercado no se ignora: se calcula probabilidad implicita sin vig y se mezcla con el modelo. Esto reduce overconfidence.
- Los picks se filtran por rangos de cuota. ML/RL aceptan principalmente cuotas entre 1.88 y 2.12; TOTAL acepta 1.75 a 2.20.
- Los totales tienen prioridad estructural en `_mejor_pick`: se asigna prioridad 2 contra prioridad 1 de ML/RL.

## Filosofia de riesgo

- Kelly existe, pero fraccionado y con techo duro: `KELLY_FRACCION=0.18`, `KELLY_MAX_STAKE_PCT=1.25` en `analysis.value`.
- Luego el staking final usa porcentajes enteros conservadores (`MIN_STAKE_PCT`, `MAX_STAKE_PCT`) mediante `IntegerPercentStaking`.
- `utils.risk_management` limita picks activos, stake por pick y exposicion diaria.
- Si el movimiento de linea contradice el pick, el riesgo desactiva el pick.
- Si hay flags de calidad de datos, el stake puede reducirse y los totales pueden bloquearse cuando ambos lados tienen fallbacks criticos.

## Filosofia de simulaciones

- Poisson modela carreras como conteos discretos independientes.
- ML: suma escenarios `h > a` y `a > h`; normaliza excluyendo empates (`total_decidido`).
- RL: suma escenarios donde `runs_team + handicap > runs_opp`.
- TOTAL: usa distribucion Poisson de la suma total con `sf(linea)` para Over y `cdf(linea - 1)` para Under; el push queda excluido para Under cuando la linea es entera.
- El sistema prefiere Poisson puro por estabilidad; ensemble esta disponible pero apagado.

## Filosofia de bankroll

- El bankroll es ledger-based: cada pick tiene `bankroll_before`, `stake_amount`, `profit_amount`, `bankroll_after`.
- El ROI se calcula sobre stake total resuelto, no sobre numero de picks.
- `yield_pct` por pick equivale a profit/stake.
- El drawdown se calcula contra el high-water mark de la equity curve.
- Se exporta historia y resumen mensual para monitorear sostenibilidad, no solo aciertos.

## Decisiones de negocio detras del codigo

- Priorizar picks con valor economico sobre picks populares: EV y edge son filtros centrales.
- Evitar sobrerreaccion a muestras pequenas: clamps, defaults, regresion de park factor hacia 1.0, H2H/contexto apagados por default.
- Ser operativo diariamente: caches y fallbacks mantienen el pipeline vivo aunque fallen endpoints.
- Registrar todo para auditar: predicciones CSV, ROI ledger, snapshots de linea y logs diarios.
- Separar diagnostico de accion: ML/RL/TOTAL pueden calcularse, pero `mejor_pick` y riesgo deciden si entra al tracking.
