import sys
import os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

# ── Logger — primer import ────────────────────────────────────────────────────
from utils.logger import configurar, get as get_log
log = configurar(nivel_consola="INFO", nivel_archivo="DEBUG")

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
    inicializar_tracking, registrar_pick,
    calcular_roi, actualizar_resultados,
)


def main():
    log.info("=" * 55)
    log.info("Iniciando análisis de predicciones MLB")
    log.info("=" * 55)

    # 0. Stats avanzadas
    log.info("Cargando stats avanzadas (FIP, wRC+)...")
    cargar_statcast()

    # 1. Pitchers + filtro TBD
    log.info("Analizando pitchers del día...")
    partidos     = analizar_pitchers()
    total_raw    = len(partidos)
    partidos_tbd = [p for p in partidos if not p.get('pitchers_confirmados')]
    partidos     = [p for p in partidos if p.get('pitchers_confirmados')]

    if partidos_tbd:
        log.warning(f"{len(partidos_tbd)} partido(s) excluido(s) por TBD:")
        for p in partidos_tbd:
            log.warning(f"  {p['away_team']} @ {p['home_team']} "
                        f"(home={p['home_pitcher']}, away={p['away_pitcher']})")

    log.info(f"Partidos válidos: {len(partidos)} / {total_raw}")

    if not partidos:
        log.error("Sin partidos válidos. Abortando.")
        return

    # 2. Pipeline
    log.info("Analizando ofensiva...")
    partidos = analizar_ofensiva(partidos)

    log.info("Analizando defensiva...")
    partidos = analizar_defensiva(partidos)

    log.info("Proyectando totales...")
    partidos = proyectar_totales(partidos)

    log.info("Analizando contexto ambiental...")
    partidos = analizar_contexto(partidos)

    log.info("Aplicando simulaciones Poisson...")
    partidos = aplicar_simulaciones(partidos)

    log.info("Analizando H2H...")
    partidos = analizar_h2h(partidos)

    # 3. Cuotas
    log.info("Obteniendo cuotas (The Odds API)...")
    cuotas   = obtener_cuotas()
    partidos = analizar_mercados(partidos, cuotas)

    # 4. Filtrar sin cuotas
    partidos = [
        p for p in partidos if any([
            isinstance(p.get("cuota_home"),    (int, float)),
            isinstance(p.get("cuota_away"),    (int, float)),
            isinstance(p.get("cuota_over"),    (int, float)),
            isinstance(p.get("cuota_rl_home"), (int, float)),
            isinstance(p.get("cuota_rl_away"), (int, float)),
        ])
    ]

    if not partidos:
        log.error("Sin partidos con cuotas útiles. Verifica la API.")
        return

    log.info(f"Partidos con cuotas disponibles: {len(partidos)}")

    # 5. Valor esperado
    log.info("Calculando valor esperado y picks...")
    partidos = analizar_valor(partidos)

    # 6. Asegurar cuotas planas
    for p in partidos:
        ho = p["home_team"]
        aw = p["away_team"]
        m  = p.get("mercados", {})
        p["cuota_home"]    = p.get("cuota_home")    or m.get(f"ml_{ho}")
        p["cuota_away"]    = p.get("cuota_away")    or m.get(f"ml_{aw}")
        p["cuota_rl_home"] = p.get("cuota_rl_home") or m.get(f"rl_{ho}")
        p["cuota_rl_away"] = p.get("cuota_rl_away") or m.get(f"rl_{aw}")

    # 7. ROI tracking
    log.info("Actualizando resultados anteriores...")
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
            seleccion = p.get("pick_rl", "")
            cuota     = (p.get("cuota_rl_home") if seleccion == p["home_team"]
                         else p.get("cuota_rl_away")) or 1.91
            prob      = (p.get("prob_home_win") if seleccion == p["home_team"]
                         else p.get("prob_away_win")) or 0.50
            valor     = p.get("valor_rl", 0)
        elif mejor.startswith("TOTAL:"):
            mercado   = "TOTAL"
            pick_t    = p.get("pick_total", "")
            linea     = p.get("linea_total", "")
            seleccion = f"{pick_t} {linea}".strip()
            cuota     = (p.get("cuota_over") if pick_t == "Over"
                         else p.get("cuota_under")) or 1.91
            prob      = 0.52
            valor     = p.get("valor_total", 0)

        registrar_pick(
            fecha=TODAY,
            juego=f"{p['away_team']} @ {p['home_team']}",
            mercado=mercado, seleccion=seleccion,
            cuota=cuota, probabilidad=prob,
            valor=valor, resultado="pendiente",
        )

    stats = calcular_roi()
    log.info(
        f"ROI | Resueltos: {stats['total_apuestas']} | "
        f"Wins: {stats.get('wins','?')} | "
        f"ROI: {stats['roi']}% | "
        f"Ganancia: {stats['ganancias']} u | "
        f"Pendientes: {stats.get('pendientes','?')}"
    )

    # 8. CSV
    columnas_clave = [
        "start_time", "home_team", "away_team",
        "home_pitcher", "away_pitcher",
        "proj_home", "proj_away",
        "prob_home_win", "prob_away_win",
        "linea_total", "pick_total", "valor_total", "stake_pct_total",
        "pick_ml",  "valor_ml",  "stake_pct_ml",
        "pick_rl",  "valor_rl",  "stake_pct_rl",
        "mejor_pick",
        "cuota_home", "cuota_away",
        "cuota_over", "cuota_under",
        "cuota_rl_home", "cuota_rl_away",
        "kelly_ml", "kelly_rl",
        "park_factor_usado",
    ]
    df        = pd.DataFrame(partidos)
    faltantes = [c for c in columnas_clave if c not in df.columns]
    if faltantes:
        log.error(f"Columnas faltantes: {faltantes}")
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
        stake_info = ""
        if mejor.startswith("ML:")    and p.get("stake_pct_ml",    0) > 0:
            stake_info = f" | Stake: {p['stake_pct_ml']}%"
        elif mejor.startswith("RL:")  and p.get("stake_pct_rl",    0) > 0:
            stake_info = f" | Stake: {p['stake_pct_rl']}%"
        elif mejor.startswith("TOTAL:") and p.get("stake_pct_total", 0) > 0:
            stake_info = f" | Stake: {p['stake_pct_total']}%"

        linea = p.get('linea_total', 'N/D')
        nivel = log.info if stake_info else log.debug

        nivel(f"{p['home_team']} vs {p['away_team']}")
        log.debug(f"  Pitchers : {p['away_pitcher']} vs {p['home_pitcher']}")
        log.debug(f"  Proy     : {p['proj_home']:.2f} - {p['proj_away']:.2f}")
        log.debug(f"  ML pick  : {p['pick_ml']} (EV {p['valor_ml']:.1f})")
        log.debug(f"  RL pick  : {p['pick_rl']} (EV {p['valor_rl']:.1f})")
        log.debug(f"  Total    : {p['pick_total']} {linea}")
        nivel(f"  ✔ {mejor}{stake_info}")

    # 10. Telegram
    log.info("Enviando picks a Telegram...")
    ok = enviar_picks(partidos, stats)
    if ok:
        log.info("Telegram: picks enviados.")
    else:
        log.warning("Telegram: notificación omitida (revisa .env).")

    log.info("Pipeline completado.")


if __name__ == '__main__':
    main()