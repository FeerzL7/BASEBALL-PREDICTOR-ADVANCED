# data/line_movement.py
#
# Detecta movimiento de línea comparando snapshots de cuotas a lo largo del día.
#
# Cómo funciona (sin créditos extra):
#   - Cada vez que main.py llama a obtener_cuotas(), este módulo guarda
#     un snapshot con timestamp en output/line_snapshots/YYYY-MM-DD.json
#   - En ejecuciones posteriores del mismo día, compara el snapshot actual
#     con el más antiguo del día (apertura) y detecta movimientos
#
# Señales que detecta:
#   TOTAL LINE MOVE  → la línea de totales cambió (ej 8.5 → 8.0)
#   JUICE SHIFT      → la línea no cambió pero el juice se movió
#                      (ej Over 1.95 → 1.87 sin mover la línea = dinero en Under)
#   ML MOVE          → la cuota de ML se acortó/alargó significativamente
#   REVERSE LINE     → la línea se mueve contra el volumen público visible
#                      (señal de sharp money)

import json
import os
from datetime import datetime, timezone
from typing import Optional

from utils.logger import get as get_log

log = get_log()

SNAPSHOTS_DIR  = "output/line_snapshots"
UMBRAL_ML_MOVE = 0.06   # movimiento mínimo en cuota ML para considerarlo significativo
UMBRAL_JU_MOVE = 0.04   # movimiento mínimo en juice (precio sin mover línea)


# ── Extracción de líneas desde el JSON de The Odds API ─────────────────────────

def _mejor_cuota(bookmakers: list, mercado: str, outcome_name: str) -> Optional[float]:
    """Devuelve la mejor cuota disponible para un outcome en un mercado."""
    mejor = None
    for book in bookmakers:
        for market in book.get('markets', []):
            if market['key'] != mercado:
                continue
            for outcome in market.get('outcomes', []):
                if outcome['name'].lower() == outcome_name.lower():
                    precio = outcome.get('price')
                    if precio and (mejor is None or precio > mejor):
                        mejor = precio
    return mejor


def _linea_total(bookmakers: list) -> Optional[float]:
    """Devuelve la línea de totales más común entre bookmakers."""
    lineas = []
    for book in bookmakers:
        for market in book.get('markets', []):
            if market['key'] != 'totals':
                continue
            for outcome in market.get('outcomes', []):
                if 'over' in outcome['name'].lower():
                    pt = outcome.get('point')
                    if pt is not None:
                        lineas.append(float(pt))
    if not lineas:
        return None
    # La línea más frecuente (consenso de mercado)
    return max(set(lineas), key=lineas.count)


def _extraer_snapshot_evento(evento: dict) -> dict:
    """Extrae las cuotas clave de un evento para guardar como snapshot."""
    bm = evento.get('bookmakers', [])
    ht = evento.get('home_team', '')
    aw = evento.get('away_team', '')
    return {
        'game_id':    evento.get('id', ''),
        'home_team':  ht,
        'away_team':  aw,
        'commence':   evento.get('commence_time', ''),
        'total_line': _linea_total(bm),
        'over_price': _mejor_cuota(bm, 'totals', 'over'),
        'under_price':_mejor_cuota(bm, 'totals', 'under'),
        'home_ml':    _mejor_cuota(bm, 'h2h', ht),
        'away_ml':    _mejor_cuota(bm, 'h2h', aw),
        'home_rl':    _mejor_cuota(bm, 'spreads', ht),
        'away_rl':    _mejor_cuota(bm, 'spreads', aw),
    }


# ── Persistencia de snapshots ──────────────────────────────────────────────────

def _ruta_snapshot(fecha: str) -> str:
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    return os.path.join(SNAPSHOTS_DIR, f"{fecha}.json")


def _cargar_snapshots(fecha: str) -> list:
    ruta = _ruta_snapshot(fecha)
    if not os.path.exists(ruta):
        return []
    with open(ruta, encoding='utf-8') as f:
        return json.load(f)


def _guardar_snapshot(fecha: str, snapshot: dict):
    ruta  = _ruta_snapshot(fecha)
    datos = _cargar_snapshots(fecha)
    datos.append(snapshot)
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)


def guardar_snapshot_diario(cuotas_api: list):
    """
    Llama a esto justo después de obtener_cuotas() en main.py.
    Guarda un snapshot timestamped de todas las líneas actuales.
    """
    if not cuotas_api:
        return

    fecha     = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now(timezone.utc).isoformat()

    snapshot_dia = {
        'timestamp': timestamp,
        'eventos':   [_extraer_snapshot_evento(ev) for ev in cuotas_api],
    }
    _guardar_snapshot(fecha, snapshot_dia)
    log.debug(f"Snapshot de líneas guardado: {len(cuotas_api)} eventos @ {timestamp[:16]}")


# ── Detección de movimiento ────────────────────────────────────────────────────

def _movimiento_total(ap: dict, ac: dict) -> Optional[dict]:
    """Detecta movimiento en la línea de totales o en el juice."""
    lt_ap = ap.get('total_line')
    lt_ac = ac.get('total_line')
    op_ap = ap.get('over_price')
    op_ac = ac.get('over_price')
    up_ap = ap.get('under_price')
    up_ac = ac.get('under_price')

    if lt_ap is None or lt_ac is None:
        return None

    # Movimiento de línea
    if lt_ac != lt_ap:
        diff  = round(lt_ac - lt_ap, 1)
        dir_  = 'SUBE' if diff > 0 else 'BAJA'
        señal = 'dinero en OVER' if diff > 0 else 'dinero en UNDER'
        return {
            'tipo':    'TOTAL_LINE_MOVE',
            'detalle': f"Total {lt_ap} → {lt_ac} ({dir_}) — {señal}",
            'fuerza':  abs(diff),
        }

    # Juice shift (línea estable pero precio se mueve)
    if op_ap and op_ac and up_ap and up_ac:
        diff_over  = round(op_ac  - op_ap,  3)
        diff_under = round(up_ac  - up_ap,  3)

        # Si Over baja de precio → dinero en Under (el libro balancea)
        if diff_over < -UMBRAL_JU_MOVE and diff_under > UMBRAL_JU_MOVE:
            return {
                'tipo':    'JUICE_SHIFT',
                'detalle': f"Over {op_ap} → {op_ac} | Under {up_ap} → {up_ac} — dinero en UNDER",
                'fuerza':  abs(diff_over),
            }
        if diff_under < -UMBRAL_JU_MOVE and diff_over > UMBRAL_JU_MOVE:
            return {
                'tipo':    'JUICE_SHIFT',
                'detalle': f"Over {op_ap} → {op_ac} | Under {up_ap} → {up_ac} — dinero en OVER",
                'fuerza':  abs(diff_under),
            }

    return None


def _movimiento_ml(ap: dict, ac: dict) -> Optional[dict]:
    """Detecta movimiento significativo en las cuotas de moneyline."""
    hm_ap = ap.get('home_ml')
    hm_ac = ac.get('home_ml')
    am_ap = ap.get('away_ml')
    am_ac = ac.get('away_ml')

    if not all([hm_ap, hm_ac, am_ap, am_ac]):
        return None

    diff_home = round(hm_ac - hm_ap, 3)# type: ignore
    diff_away = round(am_ac - am_ap, 3)# type: ignore

    # Home se acorta (baja de 2.10 a 1.90) → dinero en home
    if diff_home < -UMBRAL_ML_MOVE:
        return {
            'tipo':    'ML_MOVE',
            'detalle': f"Home ML {hm_ap} → {hm_ac} (se acorta) — dinero en {ac['home_team']}",
            'fuerza':  abs(diff_home),
        }
    # Away se acorta → dinero en away
    if diff_away < -UMBRAL_ML_MOVE:
        return {
            'tipo':    'ML_MOVE',
            'detalle': f"Away ML {am_ap} → {am_ac} (se acorta) — dinero en {ac['away_team']}",
            'fuerza':  abs(diff_away),
        }
    # Home se alarga → dinero en away (mercado aleja al home)
    if diff_home > UMBRAL_ML_MOVE:
        return {
            'tipo':    'ML_MOVE',
            'detalle': f"Home ML {hm_ap} → {hm_ac} (se alarga) — dinero en {ac['away_team']}",
            'fuerza':  abs(diff_home),
        }

    return None


def analizar_movimiento(fecha: str = None) -> dict: # type: ignore
    """
    Compara el primer snapshot del día (apertura) con el más reciente (actual).
    Devuelve dict: {game_id: [movimientos]} para todos los partidos con movimiento.

    Se puede llamar sin argumentos — usa la fecha de hoy por defecto.
    """
    if fecha is None:
        fecha = datetime.now().strftime('%Y-%m-%d')

    snapshots = _cargar_snapshots(fecha)

    if len(snapshots) < 2:
        log.debug("Sin suficientes snapshots para detectar movimiento (necesita >= 2).")
        return {}

    apertura = {ev['game_id']: ev for ev in snapshots[0]['eventos']}
    actual   = {ev['game_id']: ev for ev in snapshots[-1]['eventos']}

    ts_ap = snapshots[0]['timestamp'][:16]
    ts_ac = snapshots[-1]['timestamp'][:16]
    log.debug(f"Comparando apertura {ts_ap} vs actual {ts_ac}")

    movimientos = {}

    for game_id, ev_ac in actual.items():
        ev_ap = apertura.get(game_id)
        if not ev_ap:
            continue

        partido_movs = []

        mov_total = _movimiento_total(ev_ap, ev_ac)
        if mov_total:
            partido_movs.append(mov_total)

        mov_ml = _movimiento_ml(ev_ap, ev_ac)
        if mov_ml:
            partido_movs.append(mov_ml)

        if partido_movs:
            key = f"{ev_ac['away_team']} @ {ev_ac['home_team']}"
            movimientos[key] = {
                'movimientos': partido_movs,
                'apertura':    ev_ap,
                'actual':      ev_ac,
            }
            for mov in partido_movs:
                log.info(
                    f"[LINEA] {key} | {mov['tipo']}: {mov['detalle']}"
                )

    if not movimientos:
        log.debug("Sin movimientos de línea detectados.")

    return movimientos


# ── Integración con el modelo: ajuste de picks ────────────────────────────────

def ajustar_picks_por_movimiento(partidos: list, movimientos: dict) -> list:
    """
    Enriquece cada partido con los movimientos detectados y ajusta
    la confianza del pick si el movimiento confirma o contradice la selección.

    Factores de ajuste:
      +10% confianza si el movimiento de línea confirma el pick del modelo
      -15% confianza si el movimiento contradice el pick (señal de alerta)
    """
    for partido in partidos:
        home = partido.get('home_team', '')
        away = partido.get('away_team', '')
        clave = f"{away} @ {home}"

        partido['line_movement'] = []
        partido['mov_confirma']  = False
        partido['mov_contradice'] = False

        info = movimientos.get(clave)
        if not info:
            continue

        movs = info['movimientos']
        partido['line_movement'] = movs
        mejor_pick = partido.get('mejor_pick', 'Ninguno')

        for mov in movs:
            tipo    = mov['tipo']
            detalle = mov['detalle'].lower()

            # ── Totales ───────────────────────────────────────────────────────
            if 'TOTAL' in mejor_pick:
                pick_dir = partido.get('pick_total', '').lower()

                if tipo in ('TOTAL_LINE_MOVE', 'JUICE_SHIFT'):
                    mov_dir = 'over' if 'over' in detalle else 'under'
                    if mov_dir == pick_dir:
                        partido['mov_confirma']  = True
                        log.info(f"[CONFIRMA] {clave} — movimiento confirma {pick_dir.upper()}")
                    else:
                        partido['mov_contradice'] = True
                        log.warning(
                            f"[ALERTA] {clave} — modelo dice {pick_dir.upper()} "
                            f"pero el mercado mueve hacia {mov_dir.upper()}"
                        )

            # ── ML / RL ───────────────────────────────────────────────────────
            elif 'ML:' in mejor_pick or 'RL:' in mejor_pick:
                pick_equipo = (
                    partido.get('pick_rl', '') if 'RL:' in mejor_pick
                    else partido.get('pick_ml', '')
                ).lower()

                if tipo == 'ML_MOVE':
                    if pick_equipo and pick_equipo in detalle:
                        partido['mov_confirma']  = True
                        log.info(f"[CONFIRMA] {clave} — movimiento ML confirma {pick_equipo}")
                    elif pick_equipo:
                        partido['mov_contradice'] = True
                        log.warning(
                            f"[ALERTA] {clave} — modelo dice {pick_equipo} "
                            f"pero el ML se mueve en dirección contraria"
                        )

    return partidos


# ── Resumen para Telegram / logs ───────────────────────────────────────────────

def resumen_movimientos(movimientos: dict) -> str:
    """Genera un texto compacto con los movimientos del día para incluir en el log."""
    if not movimientos:
        return "Sin movimientos de línea detectados."

    lineas = [f"Movimientos de línea detectados ({len(movimientos)} partido(s)):"]
    for partido, info in movimientos.items():
        for mov in info['movimientos']:
            lineas.append(f"  {partido}: {mov['detalle']}")
    return "\n".join(lineas)
