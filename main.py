from analysis.pitching import analizar_pitchers 
from analysis.context import analizar_contexto
from analysis.defense import analizar_defensiva
from analysis.h2h import analizar_h2h
from analysis.markets import analizar_mercados
from analysis.value import analizar_valor
from data.odds_api import obtener_cuotas
from utils.constants import TODAY
from analysis.offense import analizar_ofensiva
from analysis.projections import proyectar_totales
from analysis.simulation import aplicar_simulaciones
from tracking.roi_tracker import inicializar_tracking, registrar_pick, calcular_roi

import pandas as pd
import os

def main():
    print("[INFO] Iniciando análisis de predicciones MLB...\n")
    
    # 1. Análisis estadístico
    partidos = analizar_pitchers()
    partidos = analizar_ofensiva(partidos)
    partidos = analizar_defensiva(partidos)
    partidos = proyectar_totales(partidos)
    partidos = analizar_contexto(partidos)
    partidos = aplicar_simulaciones(partidos)
    partidos = analizar_h2h(partidos)

    # 2. Obtener cuotas y mercados
    cuotas = obtener_cuotas()
    partidos = analizar_mercados(partidos, cuotas)

    #print(f"[DEBUG] Total de partidos antes del filtrado por cuotas: {len(partidos)}")

    # 3. Filtrar partidos sin cuotas útiles
    partidos = [
        p for p in partidos
        if any([
            isinstance(p.get("cuota_home"), (int, float)),
            isinstance(p.get("cuota_away"), (int, float)),
            isinstance(p.get("cuota_over"), (int, float)),
            isinstance(p.get("cuota_rl_home"), (int, float)),
            isinstance(p.get("cuota_rl_away"), (int, float))
        ])
    ]

    #print(f"[DEBUG] Total de partidos DESPUÉS del filtrado por cuotas: {len(partidos)}")
    if not partidos:
        print("[ERROR] No hay partidos válidos con cuotas útiles. Verifica si la API devolvió datos correctos.")
        return

    # 4. Análisis de valor
    partidos = analizar_valor(partidos)

    # 5. Asegurar que cuotas planas estén siempre
    for p in partidos:
        ho = p["home_team"]
        aw = p["away_team"]
        mercados = p.get("mercados", {})

        p["cuota_home"] = p.get("cuota_home") or mercados.get(f"ml_{ho}")
        p["cuota_away"] = p.get("cuota_away") or mercados.get(f"ml_{aw}")
        p["cuota_rl_home"] = p.get("cuota_rl_home") or mercados.get(f"rl_{ho}")
        p["cuota_rl_away"] = p.get("cuota_rl_away") or mercados.get(f"rl_{aw}")

    # 6. Inicializar tracking
    inicializar_tracking()
    for p in partidos:
        mejor = p.get("mejor_pick")
        if isinstance(mejor, dict):
            registrar_pick(
                fecha=TODAY,
                juego=f"{p['away_team']} @ {p['home_team']}",
                mercado=mejor.get("mercado", ""),
                seleccion=mejor.get("selección", ""),
                cuota=mejor.get("cuota", 1.91),
                probabilidad=mejor.get("prob", 0.50),
                valor=mejor.get("valor", 0),
                resultado="pendiente"
            )

    stats = calcular_roi()
    print(f"📊 ROI Tracking → Apuestas: {stats['total_apuestas']} | ROI: {stats['roi']}% | Ganancias: {stats['ganancias']}\n")

    # 7. Guardar CSV
    columnas_clave = [
        "start_time", "home_team", "away_team",
        "home_pitcher", "away_pitcher",
        "proj_home", "proj_away",
        "prob_home_win", "prob_away_win",
        "linea_total", "pick_total",
        "pick_ml", "valor_ml", "stake_pct_ml",
        "pick_rl", "valor_rl", "stake_pct_rl",
        "mejor_pick", "cuota_home", "cuota_away",
        "cuota_over", "cuota_under",
        "cuota_rl_home", "cuota_rl_away",
        "kelly_ml", "kelly_rl","park_factor_usado"
    ]

    df = pd.DataFrame(partidos)
    #print("[DEBUG] Columnas reales en el DataFrame:", df.columns.tolist()) 

    columnas_faltantes = [col for col in columnas_clave if col not in df.columns]
    if columnas_faltantes:
        print(f"[ERROR] No se pueden exportar resultados. Faltan columnas: {columnas_faltantes}")
    else:
        os.makedirs("output", exist_ok=True)
        df[columnas_clave].to_csv(f"output/predicciones_{TODAY}.csv", index=False, encoding='utf-8-sig')
        print("[INFO] Predicciones guardadas en output/")

    # 8. Mostrar picks
    print("\n🧠 Picks del día:\n")
    for p in partidos:
        print(f"🧠 {p['home_team']} vs {p['away_team']}")
        print(f"   🧑‍💼 Pitchers: {p['away_pitcher']} ({p['away_team']}) vs {p['home_pitcher']} ({p['home_team']})")
        print(f"   💸 Cuotas ML: {p['home_team']} @ {p.get('cuota_home', 'N/D')} | {p['away_team']} @ {p.get('cuota_away', 'N/D')}")
        print(f"   🧾 Cuotas RL: {p['home_team']} RL @ {p.get('cuota_rl_home', 'N/D')} | {p['away_team']} RL @ {p.get('cuota_rl_away', 'N/D')}")
        linea = p.get('linea_total', 'N/D')
        print(f"   📊 Cuotas Totales: Over {linea} @ {p.get('cuota_over', 'N/D')} | Under {linea} @ {p.get('cuota_under', 'N/D')}")
        print(f"   🧮 Proyección: {p['proj_home']:.2f} - {p['proj_away']:.2f}")
        print(f"   📈 Total Línea: {linea} → Pick: {p['pick_total']}")
        print(f"   💰 ML: {p['pick_ml']} (Valor: {p['valor_ml']:.2f})")
        print(f"   ⚾ RL: {p['pick_rl']} (Valor: {p['valor_rl']:.2f})")

        mejor_pick = p['mejor_pick']
        stake_info = ""
        if isinstance(mejor_pick, str):
            if mejor_pick.startswith("ML:") and p.get("stake_pct_ml", 0) > 0:
                stake_info = f" (Stake sugerido: {p['stake_pct_ml']}%)"
            elif mejor_pick.startswith("RL:") and p.get("stake_pct_rl", 0) > 0:
                stake_info = f" (Stake sugerido: {p['stake_pct_rl']}%)"

        print(f"   ✅ Mejor Pick: {mejor_pick}{stake_info}\n")

if __name__ == '__main__':
    main()
