# Catalogo de funciones

Formato: funcion, archivo:linea, responsabilidad, parametros, retorno, dependencias, importancia. Incluye funciones privadas detectadas por AST.

## `main.py`

- `main` (`main.py:40`) - Orquesta el pipeline diario completo. Parametros: ninguno. Retorno: `None`. Depende de todos los modulos principales. Importancia: critica.

## `analysis/bullpen.py`

- `_calcular_bullpen` (`analysis/bullpen.py:36`) - Filtra relievers y calcula ERA/WHIP ponderados por IP. Parametros: `splits`. Retorno: `dict`. Depende de estructura MLB stats. Importancia: alta.
- `_obtener_splits_equipo` (`analysis/bullpen.py:84`) - Consulta endpoint `stats` para pitchers del equipo. Parametros: `team_id`, `season`. Retorno: `list`. Depende de `statsapi.get`. Importancia: alta.
- `obtener_bullpen` (`analysis/bullpen.py:107`) - API publica con cache por equipo/temporada. Parametros: `team_name`, `season`. Retorno: `dict`. Depende de `lookup_team`, `_obtener_splits_equipo`, `_calcular_bullpen`. Importancia: alta.
- `limpiar_cache` (`analysis/bullpen.py:148`) - Limpia cache en memoria. Parametros: ninguno. Retorno: `None`. Importancia: baja/test.

## `analysis/context.py`

- `_parse_utc` (`analysis/context.py:71`) - Convierte timestamp MLB a datetime UTC. Parametros: `value`. Retorno: `datetime | None`. Importancia: media.
- `_valor_horario` (`analysis/context.py:78`) - Extrae valor horario seguro por indice. Parametros: `hourly`, `key`, `idx`, `default`. Retorno: valor/default. Importancia: media.
- `obtener_clima` (`analysis/context.py:85`) - Consulta Open-Meteo current/hourly y devuelve temperatura/viento/condiciones. Parametros: `lat`, `lon`, `start_time`. Retorno: `dict`. Depende de `requests`. Importancia: alta.
- `analizar_contexto` (`analysis/context.py:146`) - Agrega clima, estadio y hora local a cada partido. Parametros: `partidos`. Retorno: lista mutada. Depende de coordenadas/timezones. Importancia: alta.

## `analysis/defense.py`

- `analizar_defensiva` (`analysis/defense.py:3`) - Agrega estadisticas defensivas por equipo desde MLB API. Parametros: `partidos`. Retorno: lista mutada. Depende de `lookup_team`, `get`. Importancia: media.

## `analysis/ensemble.py`

- `_coef_variacion` (`analysis/ensemble.py:63`) - Calcula desviacion relativa de carreras recientes. Parametros: `runs`. Retorno: `float`. Importancia: media.
- `_alpha_adaptativo` (`analysis/ensemble.py:79`) - Define peso Poisson segun variabilidad. Parametros: `cv`. Retorno: `float`. Importancia: media.
- `_proyeccion_regresion` (`analysis/ensemble.py:97`) - Regresion lineal simple para siguiente juego. Parametros: `runs`. Retorno: `float | None`. Importancia: media.
- `_obtener_runs_recientes` (`analysis/ensemble.py:144`) - Extrae lista de carreras recientes del partido. Parametros: `partido`, `equipo_key`. Retorno: `list[float]`. Importancia: media.
- `_ensemble_proyeccion` (`analysis/ensemble.py:165`) - Mezcla proyeccion Poisson y regresion. Parametros: `mu_poisson`, `runs_recientes`, `nombre_equipo`. Retorno: `(float, dict)`. Importancia: media/experimental.
- `ajustar_proyecciones_ensemble` (`analysis/ensemble.py:228`) - Ajusta `proj_home/proj_away` y guarda detalle. Parametros: `partidos`. Retorno: `list`. Depende de funciones anteriores. Importancia: media, apagada por default.
- `preparar_runs_lista` (`analysis/ensemble.py:283`) - Normaliza input a lista de floats. Parametros: `runs_raw`. Retorno: `list[float]`. Importancia: baja/media.

## `analysis/h2h.py`

- `analizar_h2h` (`analysis/h2h.py:3`) - Calcula historial entre equipos y promedios. Parametros: `partidos`. Retorno: lista mutada. Depende de `statsapi.get`, `lookup_team`. Importancia: media.

## `analysis/markets.py`

- `normalizar` (`analysis/markets.py:10`) - Normaliza texto sin acentos y minusculas. Parametros: `texto`. Retorno: `str`. Importancia: alta para matching.
- `match_nombre_equipo` (`analysis/markets.py:17`) - Fuzzy match de partido contra eventos. Parametros: `nombre`, `lista_opciones`. Retorno: opcion o `None`. Depende de `SequenceMatcher`. Importancia: alta.
- `extraer_mejores_cuotas` (`analysis/markets.py:29`) - Extrae mejores precios para `h2h`, `spreads` o `totals`. Parametros: `evento`, `mercado_clave`. Retorno: `dict`. Importancia: critica.
- `extraer_mercados_disponibles` (`analysis/markets.py:134`) - Normaliza todos los outcomes cargados. Parametros: `evento`. Retorno: `dict`. Importancia: alta/futuro.
- `extraer_mejores_por_mercado` (`analysis/markets.py:168`) - Mejor precio por outcome/linea/bookmaker. Parametros: `evento`. Retorno: `dict`. Importancia: alta/futuro.
- `analizar_mercados` (`analysis/markets.py:185`) - Une partidos con eventos The Odds API y agrega cuotas planas/mercados. Parametros: `partidos`, `cuotas_api`. Retorno: lista mutada. Importancia: critica.

## `analysis/offense.py`

- `_cache_ok`, `_leer_cache`, `_guardar_cache`, `_cargar_cache_si_vigente`, `_guardar_en_cache` (`analysis/offense.py:52-86`) - Manejan cache JSON de ofensiva. Parametros: segun nombre. Retorno: bool/dict/None. Importancia: media/operacional.
- `_safe` (`analysis/offense.py:97`) - Parse float con limites. Parametros: `val`, `default`, `lo`, `hi`. Retorno: `float`. Importancia: media.
- `_normalizar_resultado` (`analysis/offense.py:105`) - Aplica defaults y flags de fallback. Parametros: `resultado`, `vs_hand`. Retorno: `dict`. Importancia: alta.
- `_top_bateadores` (`analysis/offense.py:120`) - Obtiene top bateadores por PA. Parametros: `team_id`, `season`. Retorno: `list`. Depende de `statsapi.get`. Importancia: alta.
- `_split_bateador` (`analysis/offense.py:160`) - Obtiene split individual vs RHP/LHP. Parametros: `player_id`, `vs_hand`, `season`. Retorno: `dict | None`. Importancia: alta.
- `_ops_ponderado_lineup` (`analysis/offense.py:188`) - Calcula OPS ponderado por PA. Parametros: `bateadores`, `vs_hand`, `season`. Retorno: `dict | None`. Importancia: alta.
- `_runs_recientes` (`analysis/offense.py:219`) - Promedio/lista de carreras recientes. Parametros: `team_id`, `n`. Retorno: `(float, list[float])`. Importancia: alta.
- `_wrc_plus_aprox` (`analysis/offense.py:258`) - Proxy wRC+ desde OPS. Parametros: `ops`. Retorno: `float`. Importancia: media.
- `obtener_stats_ofensivas` (`analysis/offense.py:265`) - API publica de ofensiva por equipo/mano. Parametros: `team_name`, `vs_hand`, `season`. Retorno: `dict`. Importancia: critica.
- `analizar_ofensiva` (`analysis/offense.py:346`) - Agrega ofensiva home/away segun mano del abridor rival. Parametros: `partidos`. Retorno: `list`. Importancia: critica.

## `analysis/park_factors.py`

- `_cache_vigente`, `_guardar_cache`, `_leer_cache` (`analysis/park_factors.py:35-50`) - Cache 24h de park factors. Importancia: media.
- `_obtener_stats_liga` (`analysis/park_factors.py:55`) - Descarga splits home/away de liga. Parametros: `game_type`, `season`. Retorno: `dict`. Importancia: alta.
- `_nombre_a_venue` (`analysis/park_factors.py:82`) - Mapea equipo a estadio. Parametros: `team_name`. Retorno: `str`. Importancia: alta MLB.
- `calcular_park_factors` (`analysis/park_factors.py:123`) - Calcula park factors dinamicos y fallback historico. Parametros: `season`, `forzar`. Retorno: `dict`. Importancia: critica.

## `analysis/pitching.py`

- `_es_tbd` (`analysis/pitching.py:39`) - Detecta pitcher no anunciado. Parametros: `nombre`. Retorno: `bool`. Importancia: alta.
- `_safe_float` (`analysis/pitching.py:43`) - Parse float seguro. Importancia: media.
- `_stats_temporada` (`analysis/pitching.py:51`) - ERA/WHIP/K9/IP/throws temporada. Parametros: `player_id`. Retorno: `dict`. Importancia: alta.
- `_stats_recientes` (`analysis/pitching.py:76`) - ERA/WHIP ultimas salidas. Parametros: `player_id`, `n`. Retorno: `dict | None`. Importancia: alta.
- `_era_efectiva` (`analysis/pitching.py:133`) - Combina ERA temporada y reciente. Parametros: `era_temp`, `recientes`. Retorno: `float`. Importancia: critica.
- `get_pitcher_stats` (`analysis/pitching.py:147`) - API publica de stats completas de abridor. Parametros: `name`. Retorno: `dict`. Importancia: critica.
- `analizar_pitchers` (`analysis/pitching.py:218`) - Schedule diario, pitchers probables, bullpen y filtro confirmado. Retorno: `list`. Importancia: critica.

## `analysis/projections.py`

- `_ajuste_por_temperatura`, `_temperatura_efectiva`, `_ajuste_viento`, `_ajuste_nocturno`, `ajustar_park_factor` (`analysis/projections.py:97-147`) - Ajustes contextuales de park factor. Parametros: temp/venue/contexto. Retorno: factores/detalle. Importancia: media/alta, actualmente apagado por default.
- `_get_park_factors` (`analysis/projections.py:190`) - Cache local de park factors. Retorno: `dict`. Importancia: alta.
- `_era_combinada` (`analysis/projections.py:197`) - Mezcla abridor/bullpen. Retorno: `float`. Importancia: critica.
- `_clamp` (`analysis/projections.py:203`) - Limita factores. Importancia: media.
- `_f_pitcheo` (`analysis/projections.py:207`) - Factor de pitcheo rival por ERA combinada/FIP. Retorno: `float`. Importancia: critica.
- `_f_lineup` (`analysis/projections.py:213`) - Factor ofensivo por OPS/wRC+. Retorno: `float`. Importancia: critica.
- `_base_carreras` (`analysis/projections.py:219`) - Base por forma reciente y opcional H2H. Retorno: `float`. Importancia: alta.
- `proyectar_carreras` (`analysis/projections.py:228`) - Formula central de carreras esperadas. Retorno: `float`. Importancia: critica.
- `_nombre_a_venue` (`analysis/projections.py:251`) - Fallback equipo->estadio. Importancia: alta MLB.
- `proyectar_totales` (`analysis/projections.py:290`) - Agrega proyecciones y trazabilidad al partido. Retorno: `list`. Importancia: critica.

## `analysis/simulation.py`

- `simular_probabilidades` (`analysis/simulation.py:12`) - Prob ML por Poisson. Parametros: `home`, `away`, `max_runs`. Retorno: `(home, away)`. Importancia: critica.
- `simular_runline` (`analysis/simulation.py:28`) - Prob cubrir handicap. Retorno: `float`. Importancia: alta.
- `calcular_valor` (`analysis/simulation.py:38`) - EV simple. Retorno: `float`. Importancia: media/legado.
- `calcular_kelly` (`analysis/simulation.py:42`) - Kelly full en %. Retorno: `float`. Importancia: media/legado.
- `aplicar_simulaciones` (`analysis/simulation.py:52`) - Aplica probabilidades ML/RL a todos los partidos. Retorno: `list`. Importancia: critica.

## `analysis/statcast.py`

- `_cache_ok`, `_guardar`, `_leer`, `_safe` (`analysis/statcast.py:33-50`) - Infra cache/parse. Importancia: media.
- `_calcular_fip` (`analysis/statcast.py:58`) - Formula FIP aproximada. Parametros: `stat`. Retorno: `float`. Importancia: alta.
- `_hardhit_desde_slg`, `_wrc_plus_desde_ops` (`analysis/statcast.py:72-76`) - Proxies ofensivos. Retorno: `float`. Importancia: media/alta.
- `_obtener_stats_equipo` (`analysis/statcast.py:83`) - Team stats pitching/hitting. Retorno: `(dict, dict)`. Importancia: alta.
- `_procesar_pitching`, `_procesar_batting` (`analysis/statcast.py:106-127`) - Normalizan stats avanzadas. Retorno: `dict`. Importancia: alta.
- `cargar_statcast` (`analysis/statcast.py:152`) - Carga/calcula caches de stats avanzadas para equipos. Importancia: critica.
- `_buscar`, `get_pitching`, `get_batting` (`analysis/statcast.py:188-201`) - Lookup con fallback flexible. Importancia: alta.

## `analysis/value.py`

- `_calc_ev`, `_implied_prob`, `_no_vig_probs`, `_blend_prob`, `_market_edge`, `_kelly` (`analysis/value.py:65-94`) - Utilidades economicas: EV, probabilidad implicita, no-vig, mezcla modelo/mercado, edge y Kelly fraccionado. Importancia: critica.
- `_prob_ganar_poisson`, `_prob_runline_poisson`, `_prob_total_poisson` (`analysis/value.py:105-290`) - Probabilidades por mercado con Poisson. Importancia: critica.
- `_decidir_ml`, `_decidir_rl`, `_decidir_total` (`analysis/value.py:135-330`) - Evalua cada mercado, calcula EV/stake/prediccion. Importancia: critica.
- `_alertas_calidad_datos`, `_calidad_bloquea_pick` (`analysis/value.py:303-324`) - Detecta fallbacks que bloquean picks. Importancia: alta.
- `_mejor_pick` (`analysis/value.py:421`) - Selecciona candidato ganador, con prioridad estructural a TOTAL. Importancia: critica.
- `analizar_valor` (`analysis/value.py:481`) - Punto de entrada de valor para lista de partidos. Importancia: critica.

## `data`, `bankroll`, `tracking`, `backtesting`, `dashboard`, `notifications`, `utils`

- `data.line_movement`: `_normalizar_equipo`, `_mejor_cuota`, `_linea_total`, `_extraer_snapshot_evento`, `_ruta_snapshot`, `_cargar_snapshots`, `_guardar_snapshot`, `guardar_snapshot_diario`, `_movimiento_total`, `_movimiento_ml`, `analizar_movimiento`, `ajustar_picks_por_movimiento`, `resumen_movimientos`. Responsabilidad: snapshots y senales de movimiento; importancia alta.
- `data.odds_api`: `_redact_api_key`, `_api_error_message`, `_request_json`, `_odds_params`, `_merge_event_markets`, `_configured_markets`, `obtener_cuotas`. Responsabilidad: cliente The Odds API; importancia critica.
- `data.odds_markets`: `expand_market_groups`, `split_featured_and_event_markets`, `chunk_markets`. Responsabilidad: expansion de mercados; importancia alta.
- `bankroll.staking`: `mercado_mejor_pick`, `stake_key`, `valor_key`, `probabilidad_pick`, `aplicar_staking_dinamico`; metodo `IntegerPercentStaking.stake_pct`. Responsabilidad: stake entero final; importancia alta.
- `bankroll.tracker`: `_now`, `_float`, `_int`, `_round_money`, `asegurar_output`, `normalizar_registro`, `leer_registros`, `escribir_registros`, `migrar_bankroll`, `inicializar_ledger`, `clave_apuesta`, `bankroll_actual`, `calcular_profit`, `registrar_apuesta`, `liquidar_registro`, `metricas_acumuladas`, `equity_curve`, `max_drawdown_pct`, `exportar_historial_bankroll`, `_month_key`, `_monthly_stats_rows`, `exportar_estadisticas_mensuales`, `metricas_mensuales`, `exportar_reportes`. Responsabilidad: ledger financiero completo; importancia critica.
- `tracking.roi_tracker`: `inicializar_tracking`, `_picks_existentes`, `registrar_pick`, `_resolver_resultado`, `actualizar_resultados`, `calcular_roi`. Responsabilidad: compatibilidad historica y settlement con MLB scores; importancia critica.
- `backtesting.backtesting`: `_leer_roi`, `_leer_predicciones`, `_normalizar_fecha`, `_normalizar_juego`, `_extraer_picks`, `cruzar`, `_stats`, `analizar`, `_umbral_optimo`, `sugerir_umbrales`, `calibrar_value_py`, `exportar_csv`, `imprimir_reporte`, `main`. Responsabilidad: evaluacion historica y calibracion; importancia alta.
- `dashboard.roi_dashboard`: `cargar_roi`, `cargar_predicciones`, `color_roi`, `metric_card`, `badge_resultado`, `fmt_ganancia`. Responsabilidad: visualizacion Streamlit; importancia media.
- `notifications.telegram`: `_esta_configurado`, `_enviar`, `_float`, `_fmt_money`, `_fmt_pct`, `_stake_del_pick`, `_tiene_stake`, `_emoji_mercado`, `_cuota_del_pick`, `_prob_del_pick`, `_ev_del_pick`, `_formatear_partido`, `_formatear_mes`, `_formatear_resumen_roi`, `enviar_picks`. Responsabilidad: alerta de picks y ROI; importancia media.
- `utils.constants`: `_env`. Responsabilidad: cargar variables `.env`; importancia critica.
- `utils.logger`: `_ColorFormatter.format`, `_FileFormatter.format`, `configurar`, `get`. Responsabilidad: logging; importancia alta.
- `utils.mlb_api`: `get_team_stats_vs_pitch_hand`. Responsabilidad: helper legado de stats por mano; importancia baja/media.
- `utils.poisson_math`: `pmf`, `cdf`, `sf`. Responsabilidad: matematica Poisson; importancia alta.
- `utils.risk_management`: `_mercado_mejor_pick`, `_stake_key`, `_valor_key`, `aplicar_gestion_riesgo`. Responsabilidad: caps y activacion final de picks; importancia alta.
