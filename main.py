import sys
import os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')  # type: ignore

# ── Logger — primer import, antes que cualquier módulo del proyecto ────────────
from utils.logger import configurar, get as get_log
log = configurar(nivel_consola="INFO", nivel_archivo="DEBUG")

from data.line_movement import (
    guardar_snapshot_diario,
    analizar_movimiento,
    ajustar_picks_por_movimiento,
    resumen_movimientos,
)
from analysis.pitching      import analizar_pitchers
from analysis.context       import analizar_contexto
from analysis.defense       import analizar_defensiva
from analysis.h2h           import analizar_h2h
from analysis.markets       import analizar_mercados
from analysis.value         import analizar_valor
from analysis.statcast      import cargar_statcast
from data.odds_api          import obtener_cuotas
from utils.constants        import TODAY
from analysis.offense       import analizar_ofensiva
from analysis.projections   import proyectar_totales
from analysis.simulation    import aplicar_simulaciones
from notifications.telegram import enviar_picks
from tracking.roi_tracker   import (
    inicializar_tracking,
    registrar_pick,
    calcular_roi,
    actualizar_resultados,
)
from utils.risk_management import aplicar_gestion_riesgo


def main():
    log.info("=" * 55)
    log.info("Iniciando análisis de predicciones MLB")
    log.info("=" * 55)

    # 0. Stats avanzadas (FIP, wRC+ via MLB statsapi)
    log.info("Cargando stats avanzadas (FIP, wRC+)...")
    cargar_statcast()

    # 1. Pitchers del día + filtro TBD
    log.info("Analizando pitchers del día...")
    partidos     = analizar_pitchers()
    total_raw    = len(partidos)
    partidos_tbd = [p for p in partidos if not p.get('pitchers_confirmados')]
    partidos     = [p for p in partidos if p.get('pitchers_confirmados')]

    if partidos_tbd:
        log.warning(f"{len(partidos_tbd)} partido(s) excluido(s) por lanzador TBD:")
        for p in partidos_tbd:
            log.warning(
                f"  {p['away_team']} @ {p['home_team']} "
                f"(home={p['home_pitcher']}, away={p['away_pitcher']})"
            )

    log.info(f"Partidos válidos: {len(partidos)} / {total_raw}")

    if not partidos:
        log.error("Sin partidos válidos para analizar. Abortando.")
        return

    # 2. Pipeline estadístico
    log.info("Analizando ofensiva...")
    partidos = analizar_ofensiva(partidos)

    log.info("Analizando defensiva...")
    partidos = analizar_defensiva(partidos)

    log.info("Analizando historial H2H...")   # DEBE ir antes de proyectar
    partidos = analizar_h2h(partidos)

    # FIX #4 — contexto climático va ANTES de proyectar_totales
    # para que ajustar_park_factor() tenga temperatura y viento reales.
    # En el código anterior este paso iba DESPUÉS, dejando contexto={}
    # durante toda la proyección y anulando los ajustes de temperatura/estadio.
    log.info("Analizando contexto ambiental...")
    partidos = analizar_contexto(partidos)

    log.info("Proyectando totales...")
    partidos = proyectar_totales(partidos)

    log.info("Aplicando simulaciones Poisson...")
    partidos = aplicar_simulaciones(partidos)

    # 3. Cuotas + snapshot de línea
    log.info("Obteniendo cuotas (The Odds API)...")
    cuotas = obtener_cuotas()

    # Guardar snapshot ANTES de procesar para capturar el estado actual de la línea
    guardar_snapshot_diario(cuotas)  # type: ignore

    partidos = analizar_mercados(partidos, cuotas)

    # 4. Filtrar partidos sin cuotas útiles
    partidos = [
        p for p in partidos
        if any([
            isinstance(p.get("cuota_home"),    (int, float)),
            isinstance(p.get("cuota_away"),    (int, float)),
            isinstance(p.get("cuota_over"),    (int, float)),
            isinstance(p.get("cuota_rl_home"), (int, float)),
            isinstance(p.get("cuota_rl_away"), (int, float)),
        ])
    ]

    if not partidos:
        log.error("Sin partidos con cuotas útiles. Verifica la API de odds.")
        return

    log.info(f"Partidos con cuotas disponibles: {len(partidos)}")

    # 5. Valor esperado y picks
    log.info("Calculando valor esperado y picks...")
    partidos = analizar_valor(partidos)

    # 5b. Detectar movimiento de línea y enriquecer picks
    log.info("Analizando movimiento de línea...")
    movimientos = analizar_movimiento()
    partidos    = ajustar_picks_por_movimiento(partidos, movimientos)

    if movimientos:
        log.info(resumen_movimientos(movimientos))

    partidos = aplicar_gestion_riesgo(partidos)

    # 6. Asegurar cuotas planas (fallback desde mercados)
    for p in partidos:
        ho = p["home_team"]
        aw = p["away_team"]
        m  = p.get("mercados", {})
        p["cuota_home"]    = p.get("cuota_home")    or m.get(f"ml_{ho}")
        p["cuota_away"]    = p.get("cuota_away")    or m.get(f"ml_{aw}")
        p["cuota_rl_home"] = p.get("cuota_rl_home") or m.get(f"rl_{ho}")
        p["cuota_rl_away"] = p.get("cuota_rl_away") or m.get(f"rl_{aw}")

    # 7. ROI tracking
    log.info("Actualizando resultados de picks anteriores...")
    actualizar_resultados()

    inicializar_tracking()
    for p in partidos:
        mejor = p.get("mejor_pick", "Ninguno")
        if not isinstance(mejor, str) or mejor == "Ninguno":
            continue

        mercado = seleccion = ""
        cuota = prob = 1.91
        valor = 0

        if mejor.startswith("ML:"):
            mercado   = "ML"
            seleccion = p.get("pick_ml", "")
            cuota     = (p.get("cuota_home") if seleccion == p["home_team"]
                         else p.get("cuota_away")) or 1.91
            prob      = (p.get("prob_home_win") if seleccion == p["home_team"]
                         else p.get("prob_away_win")) or 0.50
            valor     = p.get("valor_ml", 0)

        elif mejor.startswith("RL:"):
            mercado   = "RL"
            pick_rl   = p.get("pick_rl", "")
            linea_rl  = (p.get("linea_rl_home") if pick_rl == p["home_team"]
                         else p.get("linea_rl_away"))
            seleccion = f"{pick_rl} {float(linea_rl):+g}" if linea_rl is not None else pick_rl
            cuota     = (p.get("cuota_rl_home") if pick_rl == p["home_team"]
                         else p.get("cuota_rl_away")) or 1.91
            prob      = (p.get("rl_home_prob") if pick_rl == p["home_team"]
                         else p.get("rl_away_prob")) or 0.50
            valor     = p.get("valor_rl", 0)

        elif mejor.startswith("TOTAL:"):
            mercado   = "TOTAL"
            pick_t    = p.get("pick_total", "")
            linea     = p.get("linea_total", "")
            seleccion = f"{pick_t} {linea}".strip()
            cuota     = (p.get("cuota_over") if pick_t == "Over"
                         else p.get("cuota_under")) or 1.91
            prob      = p.get("prob_total") or 0.52
            valor     = p.get("valor_total", 0)

        registrar_pick(
            fecha=TODAY,
            juego=f"{p['away_team']} @ {p['home_team']}",
            mercado=mercado,
            seleccion=seleccion,
            cuota=cuota,
            probabilidad=prob,
            valor=valor,
            resultado="pendiente",
        )

    stats = calcular_roi()
    log.info(
        f"ROI | Resueltos: {stats['total_apuestas']} | "
        f"Wins: {stats.get('wins', '?')} | "
        f"ROI: {stats['roi']}% | "
        f"Ganancia: {stats['ganancias']} u | "
        f"Pendientes: {stats.get('pendientes', '?')}"
    )

    # 8. Exportar CSV
    columnas_clave = [
        "start_time", "home_team", "away_team",
        "home_pitcher", "away_pitcher",
        "proj_home", "proj_away",
        "prob_home_win", "prob_away_win",
        "linea_total", "pick_total", "valor_total", "stake_pct_total",
        "prob_total", "prob_total_raw",
        "pick_ml",  "valor_ml",  "stake_pct_ml",
        "pick_rl",  "valor_rl",  "stake_pct_rl",
        "mejor_pick",
        "riesgo_estado", "riesgo_motivo",
        "odds_event_id", "odds_loaded",
        "cuota_home", "cuota_away",
        "cuota_over", "cuota_under",
        "cuota_rl_home", "cuota_rl_away",
        "linea_rl_home", "linea_rl_away",
        "kelly_ml", "kelly_rl",
        "park_factor_usado",
        "venue_usado", "temp_efectiva", "ajuste_temp",
    ]

    df        = pd.DataFrame(partidos)
    faltantes = [c for c in columnas_clave if c not in df.columns]
    if faltantes:
        log.error(f"Columnas faltantes en el DataFrame: {faltantes}")
    else:
        os.makedirs("output", exist_ok=True)
        ruta = f"output/predicciones_{TODAY}.csv"
        df[columnas_clave].to_csv(ruta, index=False, encoding='utf-8-sig')
        log.info(f"CSV exportado → {ruta}")

    # 9. Picks en consola
    log.info("=" * 55)
    log.info("PICKS DEL DÍA")
    log.info("=" * 55)

    for p in partidos:
        mejor = p.get('mejor_pick', 'Ninguno')

        # Stake info
        stake_info = ""
        if mejor.startswith("ML:")      and p.get("stake_pct_ml",    0) > 0:
            stake_info = f" | Stake: {p['stake_pct_ml']}%"
        elif mejor.startswith("RL:")    and p.get("stake_pct_rl",    0) > 0:
            stake_info = f" | Stake: {p['stake_pct_rl']}%"
        elif mejor.startswith("TOTAL:") and p.get("stake_pct_total", 0) > 0:
            stake_info = f" | Stake: {p['stake_pct_total']}%"

        # Movimiento de línea
        mov_tag = ""
        if p.get('mov_confirma'):
            mov_tag = " | LINEA CONFIRMA"
        elif p.get('mov_contradice'):
            mov_tag = " | LINEA CONTRADICE"

        nivel = log.info if stake_info else log.debug
        linea = p.get('linea_total', 'N/D')

        nivel(f"{p['home_team']} vs {p['away_team']}")
        log.debug(f"  Pitchers : {p['away_pitcher']} vs {p['home_pitcher']}")
        log.debug(f"  Proy     : {p['proj_home']:.2f} - {p['proj_away']:.2f}")
        log.debug(f"  ML pick  : {p['pick_ml']} (EV {p['valor_ml']:.1f})")
        log.debug(f"  RL pick  : {p['pick_rl']} (EV {p['valor_rl']:.1f})")
        log.debug(f"  Total    : {p['pick_total']} {linea}")
        nivel(f"  ✔ {mejor}{stake_info}{mov_tag}")

    # 10. Notificaciones Telegram
    log.info("Enviando picks a Telegram...")
    ok = enviar_picks(partidos, stats)
    if ok:
        log.info("Telegram: picks enviados correctamente.")
    else:
        log.warning("Telegram: notificación omitida (revisa .env o conexión).")

    log.info("Pipeline completado.")


if __name__ == '__main__':
    main()
