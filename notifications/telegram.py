# notifications/telegram.py
#
# Envia a Telegram solo picks activos y acompana el mensaje con rendimiento real:
# bankroll, ROI/yield global, ganancias globales y resumen mensual.

import os
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def _esta_configurado() -> bool:
    if not _TOKEN or not _CHAT_ID:
        print("[TELEGRAM] No configurado. Define TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en .env")
        return False
    return True


def _enviar(texto: str) -> bool:
    if requests is None:
        print("[TELEGRAM] requests no instalado. Notificacion no enviada.")
        return False

    url = _BASE_URL.format(token=_TOKEN, method="sendMessage")
    try:
        resp = requests.post(url, json={
            "chat_id": _CHAT_ID,
            "text": texto,
            "parse_mode": "HTML",
        }, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            print(f"[TELEGRAM] Error API: {data.get('description', 'desconocido')}")
            return False
        return True
    except requests.exceptions.ConnectionError:
        print("[TELEGRAM] Sin conexion. Notificacion no enviada.")
        return False
    except Exception as e:
        print(f"[TELEGRAM] Error: {e}")
        return False


def _float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fmt_money(value, signed: bool = True) -> str:
    value = _float(value)
    return f"{value:+.2f}" if signed else f"{value:.2f}"


def _fmt_pct(value, signed: bool = True) -> str:
    value = _float(value)
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


def _stake_del_pick(p: dict) -> int:
    mejor = p.get("mejor_pick", "")
    if mejor.startswith("ML:"):
        return int(round(_float(p.get("stake_pct_ml"))))
    if mejor.startswith("RL:"):
        return int(round(_float(p.get("stake_pct_rl"))))
    if mejor.startswith("TOTAL:"):
        return int(round(_float(p.get("stake_pct_total"))))
    return 0


def _tiene_stake(p: dict) -> bool:
    return _stake_del_pick(p) > 0


def _emoji_mercado(pick: str) -> str:
    if pick.startswith("ML:"):
        return "$"
    if pick.startswith("RL:"):
        return "RL"
    if pick.startswith("TOTAL:"):
        return "OU"
    return "PICK"


def _cuota_del_pick(p: dict) -> float:
    mejor = p.get("mejor_pick", "")
    if mejor.startswith("ML:"):
        pick = p.get("pick_ml")
        return _float(p.get("cuota_home") if pick == p.get("home_team") else p.get("cuota_away"), 1.91)
    if mejor.startswith("RL:"):
        pick = p.get("pick_rl")
        return _float(p.get("cuota_rl_home") if pick == p.get("home_team") else p.get("cuota_rl_away"), 1.91)
    if mejor.startswith("TOTAL:"):
        pick = p.get("pick_total")
        return _float(p.get("cuota_over") if pick == "Over" else p.get("cuota_under"), 1.91)
    return 1.91


def _prob_del_pick(p: dict) -> float:
    mejor = p.get("mejor_pick", "")
    if mejor.startswith("ML:"):
        pick = p.get("pick_ml")
        key = "prob_home_win" if pick == p.get("home_team") else "prob_away_win"
        return _float(p.get(key), 0.0) * 100
    if mejor.startswith("RL:"):
        pick = p.get("pick_rl")
        key = "rl_home_prob" if pick == p.get("home_team") else "rl_away_prob"
        return _float(p.get(key), 0.0) * 100
    if mejor.startswith("TOTAL:"):
        return _float(p.get("prob_total"), 0.0) * 100
    return 0.0


def _ev_del_pick(p: dict) -> float:
    mejor = p.get("mejor_pick", "")
    if mejor.startswith("ML:"):
        return _float(p.get("valor_ml"))
    if mejor.startswith("RL:"):
        return _float(p.get("valor_rl"))
    if mejor.startswith("TOTAL:"):
        return _float(p.get("valor_total"))
    return 0.0


def _formatear_partido(p: dict, bankroll_actual: float | None = None) -> str:
    home = p["home_team"]
    away = p["away_team"]
    mejor = p.get("mejor_pick", "")
    stake_pct = _stake_del_pick(p)
    stake_amount = bankroll_actual * stake_pct / 100 if bankroll_actual and stake_pct else 0.0
    cuota = _cuota_del_pick(p)
    prob = _prob_del_pick(p)
    ev = _ev_del_pick(p)

    detail = ""
    if mejor.startswith("TOTAL:"):
        detail = f"{p.get('pick_total', '')} {p.get('linea_total', '')}".strip()
    elif mejor.startswith("RL:"):
        detail = str(p.get("pick_rl", ""))
    elif mejor.startswith("ML:"):
        detail = str(p.get("pick_ml", ""))

    movimiento = ""
    if p.get("mov_confirma"):
        movimiento = "\nLinea: confirma"
    elif p.get("mov_contradice"):
        movimiento = "\nLinea: contradice"

    return "\n".join([
        f"<b>{away} @ {home}</b>",
        f"{_emoji_mercado(mejor)} <b>{mejor}</b> | {detail}",
        f"Cuota: {cuota:.2f} | Prob: {prob:.1f}% | EV: {ev:+.1f}",
        f"Stake: <b>{stake_pct}%</b> ({_fmt_money(stake_amount, signed=False)})",
    ]) + movimiento


def _formatear_mes(mes: dict) -> str:
    if not mes:
        return "Sin resultados resueltos este mes."

    return "\n".join([
        f"<b>{mes.get('month', 'Mes actual')}</b>",
        f"Picks: {mes.get('picks', 0)} | W/L: {mes.get('wins', 0)}-{mes.get('losses', 0)} | Hit: {_fmt_pct(mes.get('hit_rate_pct'), signed=False)}",
        f"Ganancia: {_fmt_money(mes.get('profit'))} | ROI/Yield: {_fmt_pct(mes.get('roi_pct'))}",
        f"Bankroll: {_fmt_money(mes.get('bankroll_start'), signed=False)} -> {_fmt_money(mes.get('bankroll_end'), signed=False)}",
        f"Crecimiento: {_fmt_pct(mes.get('growth_pct'))} | DD max: {_fmt_pct(mes.get('max_drawdown_pct'))}",
    ])


def _formatear_resumen_roi(stats_roi: dict) -> str:
    mensual = stats_roi.get("mensual", {}) or {}
    meses = stats_roi.get("mensuales", []) or []

    lineas = [
        "<b>Rendimiento global</b>",
        f"Bankroll: <b>{_fmt_money(stats_roi.get('bankroll'), signed=False)}</b> ({_fmt_pct(stats_roi.get('growth_pct'))})",
        f"Ganancia global: <b>{_fmt_money(stats_roi.get('profit', stats_roi.get('ganancias')))}</b>",
        f"ROI/Yield: <b>{_fmt_pct(stats_roi.get('roi'))}</b> | DD max: {_fmt_pct(stats_roi.get('max_drawdown_pct'))}",
        f"Apuestas: {stats_roi.get('total_apuestas', 0)} | Wins: {stats_roi.get('wins', 0)} | Pendientes: {stats_roi.get('pendientes', 0)}",
        "",
        "<b>Rendimiento del mes</b>",
        _formatear_mes(mensual),
    ]

    ultimos = meses[-3:]
    if ultimos:
        lineas.extend(["", "<b>Ultimos meses</b>"])
        for mes in ultimos:
            lineas.append(
                f"{mes.get('month', '')}: {_fmt_money(mes.get('profit'))} | "
                f"ROI {mes.get('roi_pct', 0)}% | "
                f"{mes.get('wins', 0)}-{mes.get('losses', 0)}"
            )

    return "\n".join(lineas)


def enviar_picks(partidos: list, stats_roi: dict) -> bool:
    if not _esta_configurado():
        return False

    fecha = datetime.now().strftime("%d/%m/%Y")
    picks_con_stake = [p for p in partidos if _tiene_stake(p)]
    total = len(picks_con_stake)
    bankroll_actual = _float(stats_roi.get("bankroll"), 0.0)

    if total == 0:
        return _enviar(
            f"<b>MLB Predictor | {fecha}</b>\n\n"
            f"Sin picks con stake recomendado hoy.\n"
            f"Partidos analizados: {len(partidos)}\n\n"
            f"{_formatear_resumen_roi(stats_roi)}"
        )

    ok = _enviar(
        f"<b>MLB Predictor | {fecha}</b>\n"
        f"{total} pick{'s' if total != 1 else ''} con stake recomendado\n"
        f"Bankroll: {bankroll_actual:.2f} | ROI global: {stats_roi.get('roi', 0)}%"
    )
    if not ok:
        return False

    todos_ok = True
    for p in picks_con_stake:
        if not _enviar(_formatear_partido(p, bankroll_actual)):
            todos_ok = False

    _enviar(_formatear_resumen_roi(stats_roi))
    return todos_ok
