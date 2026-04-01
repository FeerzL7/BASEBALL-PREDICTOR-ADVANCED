# notifications/telegram.py
#
# Envía el resumen de picks del día a un bot de Telegram.
#
# Configuración (una sola vez):
#   1. Habla con @BotFather en Telegram → /newbot → copia el TOKEN
#   2. Manda cualquier mensaje a tu bot
#   3. Abre: https://api.telegram.org/bot<TOKEN>/getUpdates
#      y copia el "id" dentro de "chat" → ese es tu CHAT_ID
#   4. Crea el archivo .env en la raíz del proyecto con:
#        TELEGRAM_TOKEN=123456:ABC-xyz
#        TELEGRAM_CHAT_ID=-100xxxxxxxxx

import os
import requests
from datetime import datetime

# Carga desde variables de entorno (o .env si usas python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv es opcional

_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

_BASE_URL = "https://api.telegram.org/bot{token}/{method}"


def _esta_configurado() -> bool:
    if not _TOKEN or not _CHAT_ID:
        print("[TELEGRAM] No configurado. Define TELEGRAM_TOKEN y TELEGRAM_CHAT_ID en .env")
        return False
    return True


def _enviar(texto: str, parse_mode: str = "HTML") -> bool:
    """Envía un mensaje al chat configurado. Devuelve True si tuvo éxito."""
    url = _BASE_URL.format(token=_TOKEN, method="sendMessage")
    try:
        resp = requests.post(url, json={
            "chat_id":    _CHAT_ID,
            "text":       texto,
            "parse_mode": parse_mode,
        }, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            print(f"[TELEGRAM] Error de API: {data.get('description', 'desconocido')}")
            return False
        return True
    except requests.exceptions.ConnectionError:
        print("[TELEGRAM] Sin conexión. Notificación no enviada.")
        return False
    except Exception as e:
        print(f"[TELEGRAM] Error inesperado: {e}")
        return False


def _emoji_mercado(pick: str) -> str:
    if pick.startswith("ML:"):
        return "💰"
    if pick.startswith("RL:"):
        return "⚾"
    if pick.startswith("TOTAL:"):
        return "📊"
    return "🎯"


def _formatear_partido(p: dict) -> str:
    """Genera el bloque de texto HTML para un partido."""
    home      = p['home_team']
    away      = p['away_team']
    home_p    = p.get('home_pitcher', '?')
    away_p    = p.get('away_pitcher', '?')
    mejor     = p.get('mejor_pick', 'Ninguno')
    proj_h    = p.get('proj_home', 0)
    proj_a    = p.get('proj_away', 0)
    pf        = p.get('park_factor_usado', 1.0)
    pick_ml   = p.get('pick_ml', '-')
    val_ml    = p.get('valor_ml', 0)
    stake_ml  = p.get('stake_pct_ml', 0)
    pick_rl   = p.get('pick_rl', '-')
    val_rl    = p.get('valor_rl', 0)
    pick_tot  = p.get('pick_total', '-')
    linea     = p.get('linea_total', '-')

    emoji = _emoji_mercado(mejor)

    # Stake visible solo si el mejor pick es ML o RL
    stake_txt = ""
    if mejor.startswith("ML:") and stake_ml > 0:
        stake_txt = f" · stake {stake_ml}%"
    elif mejor.startswith("RL:") and p.get('stake_pct_rl', 0) > 0:
        stake_txt = f" · stake {p['stake_pct_rl']}%"

    lineas = [
        f"<b>{away} @ {home}</b>",
        f"<i>{away_p} vs {home_p}</i>",
        f"Proy: {proj_h:.1f} - {proj_a:.1f}  PF={pf:.2f}",
        f"ML: {pick_ml} (EV {val_ml:+.1f})  "
        f"RL: {pick_rl} (EV {val_rl:+.1f})  "
        f"Total: {pick_tot} {linea}",
        f"{emoji} <b>Pick: {mejor}{stake_txt}</b>",
    ]
    return "\n".join(lineas)


def enviar_picks(partidos: list, stats_roi: dict) -> bool:
    """
    Punto de entrada principal.
    Envía un mensaje por cada partido con pick válido,
    más un resumen de ROI al final.
    Devuelve True si todos los mensajes se enviaron correctamente.
    """
    if not _esta_configurado():
        return False

    fecha   = datetime.now().strftime("%d/%m/%Y")
    picks = [
    p for p in partidos
    if p.get('mejor_pick', 'Ninguno') != 'Ninguno'
    and (p.get('stake_pct_ml', 0) > 0 or p.get('stake_pct_rl', 0) > 0)
    ]
    total   = len(picks)

    if total == 0:
        return _enviar(f"<b>MLB · {fecha}</b>\n\nSin picks con valor positivo hoy.")

    # Encabezado
    ok = _enviar(
        f"<b>MLB Predictor · {fecha}</b>\n"
        f"{total} pick{'s' if total != 1 else ''} con valor identificado"
    )
    if not ok:
        return False

    # Un mensaje por partido con pick
    todos_ok = True
    for p in picks:
        exito = _enviar(_formatear_partido(p))
        if not exito:
            todos_ok = False

    # Resumen de ROI
    roi_txt = (
        f"\n<b>ROI acumulado</b>\n"
        f"Apuestas: {stats_roi['total_apuestas']} · "
        f"Wins: {stats_roi.get('wins', '?')} · "
        f"ROI: {stats_roi['roi']}% · "
        f"Pendientes: {stats_roi.get('pendientes', '?')}"
    )
    _enviar(roi_txt)

    return todos_ok