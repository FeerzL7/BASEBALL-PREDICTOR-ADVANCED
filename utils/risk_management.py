from utils.logger import get as get_log

log = get_log()

MAX_PICKS_DIARIOS = 3
MAX_EXPOSICION_DIARIA_PCT = 3.0
MAX_STAKE_PICK_PCT = 1.0

PRIORIDAD_MERCADO = {
    "TOTAL": 0,
    "ML": 1,
    "RL": 2,
}


def _mercado_mejor_pick(mejor_pick: str) -> str:
    if not isinstance(mejor_pick, str) or ":" not in mejor_pick:
        return ""
    return mejor_pick.split(":", 1)[0].strip().upper()


def _stake_key(mercado: str) -> str:
    return {
        "ML": "stake_pct_ml",
        "RL": "stake_pct_rl",
        "TOTAL": "stake_pct_total",
    }.get(mercado, "")


def _valor_key(mercado: str) -> str:
    return {
        "ML": "valor_ml",
        "RL": "valor_rl",
        "TOTAL": "valor_total",
    }.get(mercado, "")


def aplicar_gestion_riesgo(
    partidos: list,
    max_picks: int = MAX_PICKS_DIARIOS,
    max_exposicion_pct: float = MAX_EXPOSICION_DIARIA_PCT,
    max_stake_pick_pct: float = MAX_STAKE_PICK_PCT,
) -> list:
    """
    Limita exposicion diaria y evita picks contradichos por movimiento de linea.

    No borra el diagnostico de ML/RL/TOTAL; solo decide que picks quedan activos
    para tracking/exportacion/notificacion mediante mejor_pick y stake_pct_*.
    """
    candidatos = []

    for partido in partidos:
        mejor = partido.get("mejor_pick", "Ninguno")
        mercado = _mercado_mejor_pick(mejor)
        stake_key = _stake_key(mercado)
        valor_key = _valor_key(mercado)

        partido["riesgo_estado"] = "sin_pick"
        partido["riesgo_motivo"] = ""

        if not mercado or not stake_key:
            continue

        stake = float(partido.get(stake_key, 0) or 0)
        if stake <= 0:
            partido["mejor_pick"] = "Ninguno"
            partido["riesgo_estado"] = "descartado"
            partido["riesgo_motivo"] = "stake_no_positivo"
            continue

        if partido.get("mov_contradice"):
            partido["mejor_pick"] = "Ninguno"
            partido[stake_key] = 0.0
            partido["riesgo_estado"] = "descartado"
            partido["riesgo_motivo"] = "movimiento_contradice"
            continue

        partido[stake_key] = min(stake, max_stake_pick_pct)
        candidatos.append(partido)

    def score(partido: dict) -> tuple:
        mercado = _mercado_mejor_pick(partido.get("mejor_pick", ""))
        valor = float(partido.get(_valor_key(mercado), 0) or 0)
        confirma = 1 if partido.get("mov_confirma") else 0
        return (confirma, -PRIORIDAD_MERCADO.get(mercado, 99), valor)

    seleccionados = set()
    exposicion = 0.0

    for partido in sorted(candidatos, key=score, reverse=True):
        if len(seleccionados) >= max_picks:
            partido["mejor_pick"] = "Ninguno"
            partido["riesgo_estado"] = "descartado"
            partido["riesgo_motivo"] = "limite_picks_diarios"
            continue

        mercado = _mercado_mejor_pick(partido.get("mejor_pick", ""))
        stake_key = _stake_key(mercado)
        stake = float(partido.get(stake_key, 0) or 0)

        if exposicion + stake > max_exposicion_pct:
            stake = round(max_exposicion_pct - exposicion, 2)
            if stake <= 0:
                partido["mejor_pick"] = "Ninguno"
                partido[stake_key] = 0.0
                partido["riesgo_estado"] = "descartado"
                partido["riesgo_motivo"] = "limite_exposicion_diaria"
                continue
            partido[stake_key] = stake

        exposicion = round(exposicion + stake, 2)
        seleccionados.add(id(partido))
        partido["riesgo_estado"] = "activo"
        partido["riesgo_motivo"] = "aprobado"

    activos = sum(1 for p in partidos if p.get("riesgo_estado") == "activo")
    log.info(
        f"Gestion de riesgo: {activos} pick(s) activos | "
        f"exposicion diaria {exposicion}%"
    )
    return partidos
