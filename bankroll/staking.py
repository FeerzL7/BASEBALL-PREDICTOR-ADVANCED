from dataclasses import dataclass
from typing import Protocol

from bankroll.config import MAX_STAKE_PCT, MIN_STAKE_PCT


class StakingStrategy(Protocol):
    def stake_pct(self, partido: dict) -> int:
        ...


def mercado_mejor_pick(mejor_pick: str) -> str:
    if not isinstance(mejor_pick, str) or ":" not in mejor_pick:
        return ""
    return mejor_pick.split(":", 1)[0].strip().upper()


def stake_key(mercado: str) -> str:
    return {
        "ML": "stake_pct_ml",
        "RL": "stake_pct_rl",
        "TOTAL": "stake_pct_total",
    }.get(mercado, "")


def valor_key(mercado: str) -> str:
    return {
        "ML": "valor_ml",
        "RL": "valor_rl",
        "TOTAL": "valor_total",
    }.get(mercado, "")


def probabilidad_pick(partido: dict, mercado: str) -> float:
    if mercado == "TOTAL":
        return float(partido.get("prob_total", 0) or 0)

    if mercado == "ML":
        pick = partido.get("pick_ml")
        if pick == partido.get("home_team"):
            return float(partido.get("prob_home_win", 0) or 0)
        return float(partido.get("prob_away_win", 0) or 0)

    if mercado == "RL":
        pick = partido.get("pick_rl")
        if pick == partido.get("home_team"):
            return float(partido.get("rl_home_prob", 0) or 0)
        return float(partido.get("rl_away_prob", 0) or 0)

    return 0.0


@dataclass
class IntegerPercentStaking:
    """
    Stake modular en porcentajes enteros.

    La estrategia usa la calidad de la senal ya aprobada por value/risk:
    EV, probabilidad, mercado y movimiento de linea. Es conservadora por
    defecto y puede sustituirse por Kelly u otro modelo sin tocar el pipeline.
    """

    min_pct: int = MIN_STAKE_PCT
    max_pct: int = MAX_STAKE_PCT

    def stake_pct(self, partido: dict) -> int:
        mejor = partido.get("mejor_pick", "Ninguno")
        mercado = mercado_mejor_pick(mejor)
        key = stake_key(mercado)

        if not mercado or not key or mejor == "Ninguno":
            return 0

        if float(partido.get(key, 0) or 0) <= 0:
            return 0

        ev = float(partido.get(valor_key(mercado), 0) or 0)
        prob = probabilidad_pick(partido, mercado)
        stake = self.min_pct

        if mercado == "TOTAL":
            if ev >= 24 and prob >= 0.58:
                stake += 1
            if ev >= 34 and prob >= 0.60 and partido.get("mov_confirma"):
                stake += 1
        elif mercado == "ML":
            if ev >= 10 and prob >= 0.55:
                stake += 1
            if ev >= 16 and prob >= 0.57 and partido.get("mov_confirma"):
                stake += 1
        elif mercado == "RL":
            if ev >= 9 and prob >= 0.55:
                stake += 1
            if ev >= 14 and prob >= 0.57 and partido.get("mov_confirma"):
                stake += 1

        if partido.get("data_quality_flags"):
            stake = max(self.min_pct, stake - 1)

        return int(max(self.min_pct, min(stake, self.max_pct)))


def aplicar_staking_dinamico(
    partidos: list,
    strategy: StakingStrategy | None = None,
) -> list:
    strategy = strategy or IntegerPercentStaking()

    for partido in partidos:
        mercado = mercado_mejor_pick(partido.get("mejor_pick", ""))
        key = stake_key(mercado)
        stake = strategy.stake_pct(partido)
        partido["stake_pct_recomendado"] = stake
        partido["staking_model"] = strategy.__class__.__name__

        if key:
            partido[key] = stake

    return partidos

