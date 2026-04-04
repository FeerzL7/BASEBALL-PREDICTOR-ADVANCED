# notifications/telegram.py
#
# Envía a Telegram SOLO los picks con stake recomendado > 0.
# Ahora incluye picks de TOTAL cuando tienen stake_pct_total asignado.

import os
import requests
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
_BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def _esta_configurado() -> bool:
    if not _TOKEN or not _CHAT_ID:
        print("[TELEGRAM] No configurado. Define TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en .env")
        return False
    return True


def _enviar(texto: str) -> bool:
    url = _BASE_URL.format(token=_TOKEN, method="sendMessage")
    try:
        resp = requests.post(url, json={
            "chat_id":    _CHAT_ID,
            "text":       texto,
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


def _stake_del_pick(p: dict) -> float:
    """Devuelve el stake asignado según el tipo de mejor pick."""
    mejor = p.get('mejor_pick', '')
    if mejor.startswith('ML:'):
        return float(p.get('stake_pct_ml',    0) or 0)
    if mejor.startswith('RL:'):
        return float(p.get('stake_pct_rl',    0) or 0)
    if mejor.startswith('TOTAL:'):
        return float(p.get('stake_pct_total', 0) or 0)
    return 0.0


def _tiene_stake(p: dict) -> bool:
    """True si el pick tiene stake > 0, sea ML, RL o TOTAL."""
    return _stake_del_pick(p) > 0


def _emoji_mercado(pick: str) -> str:
    if pick.startswith('ML:'):    return '💰'
    if pick.startswith('RL:'):    return '⚾'
    if pick.startswith('TOTAL:'): return '📊'
    return '🎯'


def _formatear_partido(p: dict) -> str:
    home     = p['home_team']
    away     = p['away_team']
    home_p   = p.get('home_pitcher', '?')
    away_p   = p.get('away_pitcher', '?')
    mejor    = p.get('mejor_pick', '')
    proj_h   = p.get('proj_home', 0)
    proj_a   = p.get('proj_away', 0)
    pf       = p.get('park_factor_usado', 1.0)
    pick_ml  = p.get('pick_ml',   '-')
    val_ml   = p.get('valor_ml',  0)
    pick_rl  = p.get('pick_rl',   '-')
    val_rl   = p.get('valor_rl',  0)
    pick_tot = p.get('pick_total', '-')
    val_tot  = p.get('valor_total', 0)
    linea    = p.get('linea_total', '-')
    stake    = _stake_del_pick(p)
    emoji    = _emoji_mercado(mejor)

    # Línea de totales muestra la cuota relevante
    if mejor.startswith('TOTAL:'):
        cuota_t = (p.get('cuota_over')  if pick_tot == 'Over'
                   else p.get('cuota_under'))
        total_str = f"{pick_tot} {linea} @ {cuota_t}  (EV {val_tot:+.1f})"
    else:
        total_str = f"{pick_tot} {linea}"
        
    mov_linea = ""
    if p.get('mov_confirma'):
        mov_linea = "\nMercado confirma el pick"
    elif p.get('mov_contradice'):
        mov_linea = "\nMercado va en contra — revisar"

    return "\n".join([
        f"<b>{away} @ {home}</b>",
        f"<i>{away_p} vs {home_p}</i>",
        f"Proy: {proj_h:.1f} - {proj_a:.1f}  |  PF={pf:.2f}",
        f"ML: {pick_ml} (EV {val_ml:+.1f})   RL: {pick_rl} (EV {val_rl:+.1f})",
        f"Total: {total_str}",
        f"{emoji} <b>Pick: {mejor}  |  Stake: {stake}%</b>",
        
    ])+ mov_linea


def enviar_picks(partidos: list, stats_roi: dict) -> bool:
    """Envía a Telegram solo los picks con stake > 0 (ML, RL o TOTAL)."""
    if not _esta_configurado():
        return False

    fecha = datetime.now().strftime("%d/%m/%Y")
    picks_con_stake = [p for p in partidos if _tiene_stake(p)]
    total = len(picks_con_stake)

    if total == 0:
        return _enviar(
            f"<b>MLB · {fecha}</b>\n\n"
            f"Sin picks con stake recomendado hoy.\n"
            f"(Partidos analizados: {len(partidos)})"
        )

    ok = _enviar(
        f"<b>MLB Predictor · {fecha}</b>\n"
        f"{total} pick{'s' if total != 1 else ''} con stake recomendado"
    )
    if not ok:
        return False

    todos_ok = True
    for p in picks_con_stake:
        if not _enviar(_formatear_partido(p)):
            todos_ok = False

    _enviar(
        f"\n<b>ROI acumulado</b>\n"
        f"Apuestas: {stats_roi['total_apuestas']} · "
        f"Wins: {stats_roi.get('wins', '?')} · "
        f"ROI: {stats_roi['roi']}% · "
        f"Pendientes: {stats_roi.get('pendientes', '?')}"
    )

    return todos_ok