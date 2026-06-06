import csv
import os
from datetime import datetime
from itertools import groupby

from bankroll.config import (
    BANKROLL_HISTORY_FILE,
    INITIAL_BANKROLL,
    MONTHLY_STATS_FILE,
    ROI_FILE,
)

ROI_FIELDS = [
    "fecha", "juego", "mercado", "seleccion", "cuota",
    "probabilidad", "valor", "resultado", "ganancia",
    "stake_pct", "stake_amount",
    "bankroll_before", "bankroll_after",
    "profit_amount", "yield_pct",
    "created_at", "settled_at",
]

HISTORY_FIELDS = [
    "fecha", "juego", "mercado", "seleccion", "resultado",
    "stake_pct", "stake_amount", "profit_amount",
    "bankroll_before", "bankroll_after", "drawdown_pct",
]

MONTHLY_FIELDS = [
    "month", "picks", "wins", "losses", "pushes",
    "stake_total", "profit", "roi_pct", "yield_pct",
    "hit_rate_pct", "bankroll_start", "bankroll_end",
    "growth_pct", "max_drawdown_pct", "avg_odds",
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _round_money(value: float) -> float:
    return round(float(value), 2)


def asegurar_output():
    os.makedirs("output", exist_ok=True)


def normalizar_registro(row: dict) -> dict:
    registro = {field: row.get(field, "") for field in ROI_FIELDS}
    registro["resultado"] = registro.get("resultado") or "pendiente"
    registro["stake_pct"] = _int(registro.get("stake_pct"), 1)
    registro["cuota"] = _float(registro.get("cuota"), 0.0)
    registro["probabilidad"] = _float(registro.get("probabilidad"), 0.0)
    registro["valor"] = _float(registro.get("valor"), 0.0)
    registro["ganancia"] = _float(registro.get("ganancia"), 0.0)
    registro["stake_amount"] = _float(registro.get("stake_amount"), 0.0)
    registro["bankroll_before"] = _float(registro.get("bankroll_before"), 0.0)
    registro["bankroll_after"] = _float(registro.get("bankroll_after"), 0.0)
    registro["profit_amount"] = _float(registro.get("profit_amount"), 0.0)
    registro["yield_pct"] = _float(registro.get("yield_pct"), 0.0)
    return registro


def leer_registros(path: str = ROI_FILE) -> list[dict]:
    if not os.path.exists(path):
        return []

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        return [normalizar_registro(row) for row in reader]


def escribir_registros(registros: list[dict], path: str = ROI_FILE):
    asegurar_output()
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ROI_FIELDS)
        writer.writeheader()
        for row in registros:
            writer.writerow({field: row.get(field, "") for field in ROI_FIELDS})


def migrar_bankroll(registros: list[dict]) -> list[dict]:
    bankroll = INITIAL_BANKROLL
    migrados = []

    for row in registros:
        registro = normalizar_registro(row)
        resultado = registro.get("resultado", "pendiente")
        stake_pct = max(1, _int(registro.get("stake_pct"), 1))
        stake_amount = _float(registro.get("stake_amount"), 0.0)
        bankroll_before = _float(registro.get("bankroll_before"), 0.0)

        if bankroll_before <= 0:
            bankroll_before = bankroll

        if stake_amount <= 0:
            stake_amount = _round_money(bankroll_before * stake_pct / 100)

        if resultado in ("win", "lose", "null"):
            profit = _float(registro.get("profit_amount"), 0.0)
            if profit == 0.0 and resultado != "null":
                unidades = _float(registro.get("ganancia"), 0.0)
                if unidades == 0.0:
                    unidades, profit = calcular_profit(
                        resultado,
                        _float(registro.get("cuota"), 0.0),
                        stake_amount,
                    )
                else:
                    profit = _round_money(unidades * stake_amount)
                registro["ganancia"] = round(unidades, 4)

            bankroll_after = _float(registro.get("bankroll_after"), 0.0)
            if bankroll_after <= 0:
                bankroll_after = _round_money(bankroll_before + profit)
            bankroll = bankroll_after
            registro["profit_amount"] = _round_money(profit)
            registro["bankroll_after"] = bankroll_after
            registro["settled_at"] = registro.get("settled_at") or _now()

        registro["stake_pct"] = stake_pct
        registro["stake_amount"] = stake_amount
        registro["bankroll_before"] = _round_money(bankroll_before)
        registro["yield_pct"] = (
            round(_float(registro.get("profit_amount"), 0.0) / stake_amount * 100, 2)
            if stake_amount else 0.0
        )
        registro["created_at"] = registro.get("created_at") or ""
        migrados.append(registro)

    return migrados


def inicializar_ledger(path: str = ROI_FILE):
    asegurar_output()
    if not os.path.exists(path):
        escribir_registros([], path)
        return

    registros = migrar_bankroll(leer_registros(path))
    escribir_registros(registros, path)
    exportar_reportes(registros)


def clave_apuesta(row: dict) -> tuple:
    return (
        str(row.get("fecha", "")),
        str(row.get("juego", "")),
        str(row.get("mercado", "")),
        str(row.get("seleccion", "")),
    )


def bankroll_actual(registros: list[dict] | None = None) -> float:
    registros = registros if registros is not None else leer_registros()
    resueltos = [
        r for r in registros
        if r.get("resultado") in ("win", "lose", "null")
        and _float(r.get("bankroll_after"), 0.0) > 0
    ]
    if resueltos:
        return _round_money(_float(resueltos[-1].get("bankroll_after"), INITIAL_BANKROLL))

    profit = sum(_float(r.get("profit_amount"), 0.0) for r in registros
                 if r.get("resultado") in ("win", "lose", "null"))
    return _round_money(INITIAL_BANKROLL + profit)


def calcular_profit(resultado: str, cuota: float, stake_amount: float) -> tuple[float, float]:
    if resultado == "win":
        unidades = cuota - 1
        return unidades, _round_money(stake_amount * unidades)
    if resultado == "lose":
        return -1.0, _round_money(-stake_amount)
    if resultado == "null":
        return 0.0, 0.0
    return 0.0, 0.0


def registrar_apuesta(
    fecha,
    juego,
    mercado,
    seleccion,
    cuota,
    probabilidad,
    valor,
    stake_pct: int,
    resultado: str = "pendiente",
) -> bool:
    inicializar_ledger()
    registros = leer_registros()
    clave = (str(fecha), str(juego), str(mercado), str(seleccion))
    if clave in {clave_apuesta(r) for r in registros}:
        return False

    bankroll = bankroll_actual(registros)
    stake_pct = max(0, int(stake_pct or 0))
    stake_amount = _round_money(bankroll * stake_pct / 100)
    cuota = _float(cuota, 0.0)
    unidades, profit = calcular_profit(resultado, cuota, stake_amount)
    bankroll_after = "" if resultado == "pendiente" else _round_money(bankroll + profit)
    yield_pct = round(profit / stake_amount * 100, 2) if stake_amount else 0.0

    registros.append({
        "fecha": str(fecha),
        "juego": str(juego),
        "mercado": str(mercado),
        "seleccion": str(seleccion),
        "cuota": cuota,
        "probabilidad": _float(probabilidad, 0.0),
        "valor": _float(valor, 0.0),
        "resultado": resultado,
        "ganancia": round(unidades, 4),
        "stake_pct": stake_pct,
        "stake_amount": stake_amount,
        "bankroll_before": bankroll,
        "bankroll_after": bankroll_after,
        "profit_amount": profit,
        "yield_pct": yield_pct,
        "created_at": _now(),
        "settled_at": _now() if resultado != "pendiente" else "",
    })
    escribir_registros(registros)
    exportar_reportes(registros)
    return True


def liquidar_registro(registro: dict, resultado: str, bankroll_before: float) -> dict:
    registro = normalizar_registro(registro)
    cuota = _float(registro.get("cuota"), 0.0)
    stake_amount = _float(registro.get("stake_amount"), 0.0)
    if stake_amount <= 0:
        stake_pct = _int(registro.get("stake_pct"), 1)
        stake_amount = _round_money(bankroll_before * stake_pct / 100)

    unidades, profit = calcular_profit(resultado, cuota, stake_amount)
    bankroll_after = _round_money(bankroll_before + profit)
    yield_pct = round(profit / stake_amount * 100, 2) if stake_amount else 0.0

    registro.update({
        "resultado": resultado,
        "ganancia": round(unidades, 4),
        "stake_amount": stake_amount,
        "bankroll_before": _round_money(bankroll_before),
        "bankroll_after": bankroll_after,
        "profit_amount": profit,
        "yield_pct": yield_pct,
        "settled_at": _now(),
    })
    return registro


def metricas_acumuladas(registros: list[dict] | None = None) -> dict:
    registros = registros if registros is not None else leer_registros()
    resueltos = [r for r in registros if r.get("resultado") in ("win", "lose")]
    pushes = [r for r in registros if r.get("resultado") == "null"]
    pendientes = [r for r in registros if r.get("resultado") == "pendiente"]

    wins = sum(1 for r in resueltos if r.get("resultado") == "win")
    losses = sum(1 for r in resueltos if r.get("resultado") == "lose")
    stake_total = sum(_float(r.get("stake_amount"), 0.0) for r in resueltos)
    profit = sum(_float(r.get("profit_amount"), 0.0) for r in resueltos)
    bankroll = bankroll_actual(registros)
    hit_rate = wins / len(resueltos) * 100 if resueltos else 0.0
    roi = profit / stake_total * 100 if stake_total > 0 else 0.0
    growth = (bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100
    drawdown = max_drawdown_pct(registros)

    return {
        "total_apuestas": len(resueltos),
        "wins": wins,
        "losses": losses,
        "pushes": len(pushes),
        "pendientes": len(pendientes),
        "stake_total": round(stake_total, 2),
        "ganancias": round(profit, 2),
        "profit": round(profit, 2),
        "roi": round(roi, 2),
        "yield": round(roi, 2),
        "hit_rate": round(hit_rate, 2),
        "bankroll": round(bankroll, 2),
        "bankroll_inicial": round(INITIAL_BANKROLL, 2),
        "growth_pct": round(growth, 2),
        "max_drawdown_pct": round(drawdown, 2),
    }


def equity_curve(registros: list[dict]) -> list[dict]:
    curve = []
    high = INITIAL_BANKROLL
    for r in registros:
        if r.get("resultado") not in ("win", "lose", "null"):
            continue
        after = _float(r.get("bankroll_after"), 0.0)
        if after <= 0:
            continue
        high = max(high, after)
        drawdown = (after - high) / high * 100 if high else 0.0
        curve.append({**r, "drawdown_pct": round(drawdown, 2)})
    return curve


def max_drawdown_pct(registros: list[dict]) -> float:
    curve = equity_curve(registros)
    if not curve:
        return 0.0
    return min(_float(r.get("drawdown_pct"), 0.0) for r in curve)


def exportar_historial_bankroll(registros: list[dict]):
    asegurar_output()
    curve = equity_curve(registros)
    with open(BANKROLL_HISTORY_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_FIELDS)
        writer.writeheader()
        for row in curve:
            writer.writerow({field: row.get(field, "") for field in HISTORY_FIELDS})


def _month_key(row: dict) -> str:
    fecha = str(row.get("fecha", ""))
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(fecha, fmt).strftime("%Y-%m")
        except ValueError:
            continue
    return fecha[:7] if len(fecha) >= 7 else "unknown"


def exportar_estadisticas_mensuales(registros: list[dict]):
    asegurar_output()
    curve = equity_curve(registros)
    rows = []
    for month, group in groupby(sorted(curve, key=_month_key), key=_month_key):
        picks = list(group)
        wins = sum(1 for r in picks if r.get("resultado") == "win")
        losses = sum(1 for r in picks if r.get("resultado") == "lose")
        pushes = sum(1 for r in picks if r.get("resultado") == "null")
        resolved = wins + losses
        stake_total = sum(_float(r.get("stake_amount"), 0.0) for r in picks
                          if r.get("resultado") in ("win", "lose"))
        profit = sum(_float(r.get("profit_amount"), 0.0) for r in picks
                     if r.get("resultado") in ("win", "lose"))
        start = _float(picks[0].get("bankroll_before"), INITIAL_BANKROLL)
        end = _float(picks[-1].get("bankroll_after"), start)
        avg_odds = sum(_float(r.get("cuota"), 0.0) for r in picks) / len(picks)
        roi = profit / stake_total * 100 if stake_total else 0.0
        hit_rate = wins / resolved * 100 if resolved else 0.0
        growth = (end - start) / start * 100 if start else 0.0
        drawdown = min(_float(r.get("drawdown_pct"), 0.0) for r in picks)

        rows.append({
            "month": month,
            "picks": resolved,
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "stake_total": round(stake_total, 2),
            "profit": round(profit, 2),
            "roi_pct": round(roi, 2),
            "yield_pct": round(roi, 2),
            "hit_rate_pct": round(hit_rate, 2),
            "bankroll_start": round(start, 2),
            "bankroll_end": round(end, 2),
            "growth_pct": round(growth, 2),
            "max_drawdown_pct": round(drawdown, 2),
            "avg_odds": round(avg_odds, 3),
        })

    with open(MONTHLY_STATS_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MONTHLY_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def exportar_reportes(registros: list[dict] | None = None):
    registros = registros if registros is not None else leer_registros()
    exportar_historial_bankroll(registros)
    exportar_estadisticas_mensuales(registros)
