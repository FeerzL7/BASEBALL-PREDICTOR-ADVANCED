# backtesting/backtesting.py
#
# Cómo ejecutar:
#   python -m backtesting.backtesting
#   python -m backtesting.backtesting --desde 2025-06-01 --hasta 2025-07-15
#   python -m backtesting.backtesting --calibrar   (actualiza value.py automáticamente)
#
# Qué hace:
#   1. Lee todos los CSVs de output/predicciones_*.csv
#   2. Cruza cada pick con su resultado en roi_tracking.csv
#   3. Calcula hit rate, ROI y EV medio por mercado y por umbral de EV
#   4. Sugiere umbrales óptimos de UMBRAL_EV_ML/RL/TOTAL
#   5. Opcionalmente reescribe esas constantes en analysis/value.py

import argparse
import csv
import glob
import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Optional

from utils.logger import configurar, get as get_log

log = configurar(nivel_consola="INFO", nivel_archivo="DEBUG")

PRED_DIR  = "output"
ROI_FILE  = "output/roi_tracking.csv"
OUT_FILE  = "output/backtest_results.csv"
VALUE_PY  = "analysis/value.py"
ROI_MINIMO_UMBRAL = 0.0

# Bandas de EV para el análisis de sensibilidad
EV_BANDAS = [0, 3, 5, 7, 10, 15, 20, 30]


# ── Carga de datos ─────────────────────────────────────────────────────────────

def _leer_roi() -> dict:
    """
    Devuelve dict: (juego_normalizado, mercado, seleccion) → resultado
    donde juego_normalizado = 'away @ home' en minúsculas sin espacios extra.
    """
    resultados = {}
    if not os.path.exists(ROI_FILE):
        log.error(f"No existe {ROI_FILE}. Ejecuta main.py al menos un día primero.")
        return resultados

    with open(ROI_FILE, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            row['fecha'] = _normalizar_fecha(row.get('fecha', '').strip())
            resultado = row.get('resultado', '').strip()
            if resultado not in ('win', 'lose'):
                continue
            juego    = row.get('juego', '').strip().lower()
            mercado  = row.get('mercado', '').strip().upper()
            seleccion = row.get('seleccion', '').strip()
            # Para TOTAL, la seleccion es "Over 8.5" — guardamos solo Over/Under
            if mercado == 'TOTAL':
                seleccion = seleccion.split()[0] if seleccion else seleccion
            clave = (juego, mercado, seleccion.lower())
            # Si el mismo pick aparece varias veces (ej: duplicado corregido),
            # prevalece el más reciente (ya garantizado por roi_tracker.py)
            resultados[clave] = resultado
    log.info(f"ROI tracking: {len(resultados)} picks resueltos cargados.")
    return resultados


def _leer_predicciones(desde: Optional[str], hasta: Optional[str]) -> list:
    """Lee todos los CSVs de predicciones dentro del rango de fechas."""
    patron = os.path.join(PRED_DIR, "predicciones_*.csv")
    archivos = sorted(glob.glob(patron))
    registros = []

    for ruta in archivos:
        nombre = os.path.basename(ruta)
        m = re.search(r'(\d{4}-\d{2}-\d{2})', nombre)
        if not m:
            continue
        fecha = m.group(1)
        if desde and fecha < desde:
            continue
        if hasta and fecha > hasta:
            continue

        with open(ruta, encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                row['_fecha'] = fecha
                registros.append(row)

    log.info(f"Predicciones cargadas: {len(registros)} filas de {len(archivos)} archivos.")
    return registros


def _normalizar_fecha(fecha: str) -> str:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(fecha, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return fecha


# ── Cruce ──────────────────────────────────────────────────────────────────────

def _normalizar_juego(away: str, home: str) -> str:
    return f"{away.strip().lower()} @ {home.strip().lower()}"


def _extraer_picks(row: dict) -> list:
    """
    Extrae los picks con stake de una fila del CSV de predicciones.
    Devuelve lista de dicts con: mercado, seleccion, valor_ev, stake_pct, cuota.
    """
    picks = []
    mejor = row.get('mejor_pick', 'Ninguno').strip()
    if not mejor or mejor == 'Ninguno':
        return picks

    home = row.get('home_team', '')
    away = row.get('away_team', '')

    def safe_float(v, default=0.0):
        try:
            return float(v)
        except (ValueError, TypeError):
            return default

    if mejor.startswith('ML:'):
        picks.append({
            'mercado':  'ML',
            'seleccion': row.get('pick_ml', '').strip(),
            'valor_ev':  safe_float(row.get('valor_ml')),
            'stake_pct': safe_float(row.get('stake_pct_ml')),
            'cuota':     safe_float(row.get('cuota_home') if row.get('pick_ml') == home
                                    else row.get('cuota_away'), 1.91),
        })

    elif mejor.startswith('RL:'):
        picks.append({
            'mercado':  'RL',
            'seleccion': row.get('pick_rl', '').strip(),
            'valor_ev':  safe_float(row.get('valor_rl')),
            'stake_pct': safe_float(row.get('stake_pct_rl')),
            'cuota':     safe_float(row.get('cuota_rl_home') if row.get('pick_rl') == home
                                    else row.get('cuota_rl_away'), 1.91),
        })

    elif mejor.startswith('TOTAL:'):
        pick_t = row.get('pick_total', '').strip()
        picks.append({
            'mercado':  'TOTAL',
            'seleccion': pick_t,
            'valor_ev':  safe_float(row.get('valor_total')),
            'stake_pct': safe_float(row.get('stake_pct_total')),
            'cuota':     safe_float(row.get('cuota_over') if pick_t == 'Over'
                                    else row.get('cuota_under'), 1.91),
        })

    return picks


def cruzar(registros: list, resultados: dict) -> list:
    """
    Cruza cada fila de predicciones con su resultado real.
    Devuelve lista de dicts enriquecida con 'resultado'.
    """
    cruzados = []
    sin_resultado = 0

    for row in registros:
        home = row.get('home_team', '')
        away = row.get('away_team', '')
        juego = _normalizar_juego(away, home)

        for pick in _extraer_picks(row):
            mercado   = pick['mercado']
            seleccion = pick['seleccion']

            # Buscar en roi_tracking
            sel_buscar = seleccion.lower()
            if mercado == 'TOTAL':
                sel_buscar = seleccion.split()[0].lower() if seleccion else ''

            clave = (juego, mercado, sel_buscar)
            resultado = resultados.get(clave)

            if not resultado:
                sin_resultado += 1
                continue

            cruzados.append({
                'fecha':    row['_fecha'],
                'juego':    juego,
                'mercado':  mercado,
                'seleccion': seleccion,
                'valor_ev': pick['valor_ev'],
                'stake_pct': pick['stake_pct'],
                'cuota':    pick['cuota'],
                'resultado': resultado,
                'ganancia':  round(pick['cuota'] - 1, 4) if resultado == 'win' else -1.0,
            })

    log.info(f"Picks cruzados: {len(cruzados)} | Sin resultado aún: {sin_resultado}")
    return cruzados


# ── Análisis ───────────────────────────────────────────────────────────────────

def _stats(picks: list) -> dict:
    if not picks:
        return {'n': 0, 'wins': 0, 'hit_rate': 0.0,
                'roi': 0.0, 'ev_medio': 0.0, 'ganancia': 0.0}
    n       = len(picks)
    wins    = sum(1 for p in picks if p['resultado'] == 'win')
    gan     = sum(p['ganancia'] for p in picks)
    ev_med  = sum(p['valor_ev'] for p in picks) / n
    return {
        'n':        n,
        'wins':     wins,
        'hit_rate': round(wins / n * 100, 1),
        'roi':      round(gan / n * 100, 2),
        'ev_medio': round(ev_med, 2),
        'ganancia': round(gan, 3),
    }


def analizar(cruzados: list) -> dict:
    """
    Calcula métricas por mercado y por banda de EV.
    Devuelve dict con estructura:
      {
        'global': {...},
        'por_mercado': { 'ML': {...}, 'RL': {...}, 'TOTAL': {...} },
        'sensibilidad': {
            'ML':    { ev_umbral: stats, ... },
            'RL':    { ... },
            'TOTAL': { ... },
        }
      }
    """
    resultado = {
        'global':       _stats(cruzados),
        'por_mercado':  {},
        'sensibilidad': defaultdict(dict),
    }

    # Por mercado
    por_mercado = defaultdict(list)
    for p in cruzados:
        por_mercado[p['mercado']].append(p)

    for mercado, picks in por_mercado.items():
        resultado['por_mercado'][mercado] = _stats(picks)

    # Sensibilidad: ¿qué pasa si subimos el umbral de EV?
    for mercado, picks in por_mercado.items():
        for banda in EV_BANDAS:
            filtrados = [p for p in picks if p['valor_ev'] >= banda]
            resultado['sensibilidad'][mercado][banda] = _stats(filtrados)

    return resultado


# ── Sugerencia de umbrales óptimos ────────────────────────────────────────────

def _umbral_optimo(
    sensibilidad_mercado: dict,
    min_picks: int = 10,
    roi_minimo: float = ROI_MINIMO_UMBRAL,
) -> Optional[int]:
    """
    Busca el umbral de EV donde el ROI es máximo con al menos min_picks muestras.
    Devuelve el umbral (int) o None si no hay datos suficientes.
    """
    mejor_roi   = -999
    mejor_umbral = None

    for banda, stats in sorted(sensibilidad_mercado.items()):
        if stats['n'] < min_picks or stats['roi'] < roi_minimo:
            continue
        if stats['roi'] > mejor_roi:
            mejor_roi    = stats['roi']
            mejor_umbral = banda

    return mejor_umbral


def sugerir_umbrales(analisis: dict, min_picks: int = 10) -> dict:
    sugeridos = {}
    for mercado in ('ML', 'RL', 'TOTAL'):
        sens = analisis['sensibilidad'].get(mercado, {})
        u = _umbral_optimo(sens, min_picks=min_picks)
        sugeridos[mercado] = u
        if u is not None:
            stats = sens[u]
            log.info(
                f"Umbral óptimo {mercado}: EV >= {u} → "
                f"hit rate {stats['hit_rate']}% | ROI {stats['roi']}% "
                f"| n={stats['n']}"
            )
        else:
            log.warning(
                f"Umbral {mercado}: sin banda con ROI >= {ROI_MINIMO_UMBRAL}% "
                f"y n >= {min_picks}"
            )
    return sugeridos


# ── Calibración automática de value.py ────────────────────────────────────────

def calibrar_value_py(sugeridos: dict):
    """
    Reescribe las constantes UMBRAL_EV_ML/RL/TOTAL en analysis/value.py
    con los umbrales sugeridos por el backtesting.
    Solo modifica si el valor sugerido es distinto al actual.
    """
    if not os.path.exists(VALUE_PY):
        log.error(f"No se encontró {VALUE_PY}")
        return

    with open(VALUE_PY, encoding='utf-8') as f:
        contenido = f.read()

    MAPA = {
        'ML':    'UMBRAL_EV_ML',
        'RL':    'UMBRAL_EV_RL',
        'TOTAL': 'UMBRAL_EV_TOTAL',
    }

    cambios = 0
    for mercado, constante in MAPA.items():
        nuevo = sugeridos.get(mercado)
        if nuevo is None:
            continue
        patron = rf'({re.escape(constante)}\s*=\s*)(\d+)'
        m = re.search(patron, contenido)
        if not m:
            log.warning(f"No se encontró {constante} en {VALUE_PY}")
            continue
        actual = int(m.group(2))
        if actual == nuevo:
            log.info(f"{constante} ya es {actual} — sin cambio.")
            continue
        contenido = re.sub(patron, rf'\g<1>{nuevo}', contenido)
        log.info(f"{constante}: {actual} → {nuevo}")
        cambios += 1

    if cambios:
        with open(VALUE_PY, 'w', encoding='utf-8') as f:
            f.write(contenido)
        log.info(f"{VALUE_PY} actualizado con {cambios} cambio(s).")
    else:
        log.info("Sin cambios en value.py — umbrales ya óptimos.")


# ── Exportar CSV de resultados ─────────────────────────────────────────────────

def exportar_csv(cruzados: list, analisis: dict):
    os.makedirs(PRED_DIR, exist_ok=True)

    # Picks detallados
    with open(OUT_FILE, 'w', newline='', encoding='utf-8-sig') as f:
        campos = ['fecha', 'juego', 'mercado', 'seleccion',
                  'valor_ev', 'stake_pct', 'cuota', 'resultado', 'ganancia']
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(cruzados)

    # Resumen por mercado
    resumen_path = OUT_FILE.replace('.csv', '_resumen.csv')
    with open(resumen_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['mercado', 'n', 'wins', 'hit_rate_%',
                         'roi_%', 'ev_medio', 'ganancia_u'])
        g = analisis['global']
        writer.writerow(['GLOBAL', g['n'], g['wins'], g['hit_rate'],
                         g['roi'], g['ev_medio'], g['ganancia']])
        for mercado, s in sorted(analisis['por_mercado'].items()):
            writer.writerow([mercado, s['n'], s['wins'], s['hit_rate'],
                             s['roi'], s['ev_medio'], s['ganancia']])

    # Sensibilidad por EV
    sens_path = OUT_FILE.replace('.csv', '_sensibilidad.csv')
    with open(sens_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['mercado', 'ev_umbral', 'n', 'wins',
                         'hit_rate_%', 'roi_%', 'ganancia_u'])
        for mercado, bandas in sorted(analisis['sensibilidad'].items()):
            for banda, s in sorted(bandas.items()):
                writer.writerow([mercado, banda, s['n'], s['wins'],
                                 s['hit_rate'], s['roi'], s['ganancia']])

    log.info(f"Resultados exportados:")
    log.info(f"  {OUT_FILE}")
    log.info(f"  {resumen_path}")
    log.info(f"  {sens_path}")


# ── Reporte en consola ─────────────────────────────────────────────────────────

def imprimir_reporte(analisis: dict):
    g = analisis['global']
    log.info("=" * 55)
    log.info("BACKTESTING — RESUMEN GLOBAL")
    log.info("=" * 55)
    log.info(f"Total picks resueltos : {g['n']}")
    log.info(f"Wins                  : {g['wins']}")
    log.info(f"Hit rate              : {g['hit_rate']}%")
    log.info(f"ROI                   : {g['roi']}%")
    log.info(f"EV medio de picks     : {g['ev_medio']}")
    log.info(f"Ganancia acumulada    : {g['ganancia']} u")
    log.info("")
    log.info(f"{'Mercado':<10} {'N':>5} {'Hit%':>7} {'ROI%':>8} {'EV med':>8}")
    log.info("-" * 42)
    for mercado, s in sorted(analisis['por_mercado'].items()):
        log.info(
            f"{mercado:<10} {s['n']:>5} {s['hit_rate']:>6}% "
            f"{s['roi']:>7}% {s['ev_medio']:>8}"
        )
    log.info("")
    log.info("SENSIBILIDAD POR UMBRAL DE EV")
    log.info("-" * 42)
    for mercado in ('ML', 'RL', 'TOTAL'):
        bandas = analisis['sensibilidad'].get(mercado, {})
        if not bandas:
            continue
        log.info(f"  {mercado}:")
        for banda, s in sorted(bandas.items()):
            if s['n'] == 0:
                continue
            log.info(
                f"    EV >= {banda:>3}  →  n={s['n']:>4}  "
                f"hit={s['hit_rate']:>5}%  ROI={s['roi']:>7}%"
            )


# ── Punto de entrada ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Backtesting histórico del MLB Predictor"
    )
    parser.add_argument('--desde',    default=None,
                        help='Fecha inicio YYYY-MM-DD (incluida)')
    parser.add_argument('--hasta',    default=None,
                        help='Fecha fin YYYY-MM-DD (incluida)')
    parser.add_argument('--calibrar', action='store_true',
                        help='Actualizar umbrales en analysis/value.py')
    parser.add_argument('--min-picks', type=int, default=10,
                        help='Mínimo de picks para considerar un umbral válido')
    args = parser.parse_args()

    log.info("Iniciando backtesting histórico...")

    resultados  = _leer_roi()
    if not resultados:
        return

    registros   = _leer_predicciones(args.desde, args.hasta)
    if not registros:
        log.error("Sin predicciones en el rango indicado.")
        return

    cruzados    = cruzar(registros, resultados)
    if not cruzados:
        log.error("No se pudo cruzar ningún pick con resultados reales.")
        return

    analisis    = analizar(cruzados)
    imprimir_reporte(analisis)

    sugeridos   = sugerir_umbrales(analisis, min_picks=args.min_picks)
    exportar_csv(cruzados, analisis)

    if args.calibrar:
        calibrar_value_py(sugeridos)
    else:
        log.info("Usa --calibrar para actualizar umbrales en value.py automáticamente.")

    log.info("Backtesting completado.")


if __name__ == '__main__':
    main()
