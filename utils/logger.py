# utils/logger.py
#
# Logging estructurado para MLB Predictor.
#
# Niveles usados en el proyecto:
#   DEBUG   → datos internos de cálculo (ERA, OPS, proyecciones por partido)
#   INFO    → flujo principal del pipeline (inicio, pasos, picks finales)
#   WARNING → datos faltantes, fallbacks activados, APIs con respuesta parcial
#   ERROR   → fallos que impiden completar un paso (sin cuotas, sin partidos)
#
# Salida:
#   - Consola: nivel INFO y superior, formato compacto con color
#   - Archivo: nivel DEBUG y superior, formato completo con timestamp
#     Ruta: logs/mlb_YYYY-MM-DD.log (uno por día, rotación automática)

import logging
import os
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

# ── Colores para consola (ANSI) ───────────────────────────────────────────────
_RESET  = "\x1b[0m"
_BOLD   = "\x1b[1m"
_COLORS = {
    'DEBUG':    "\x1b[36m",    # cyan
    'INFO':     "\x1b[32m",    # verde
    'WARNING':  "\x1b[33m",    # amarillo
    'ERROR':    "\x1b[31m",    # rojo
    'CRITICAL': "\x1b[35m",    # magenta
}


class _ColorFormatter(logging.Formatter):
    """Formatter con colores ANSI para la consola."""

    FMT = "{color}{level:<8}{reset} {message}"

    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        level = record.levelname
        # Recortar módulo largo para que el log sea legible
        record.module_short = record.module[:20]
        msg = super().format(record)
        return self.FMT.format(
            color=color, level=level, reset=_RESET, message=record.getMessage()
        )


class _FileFormatter(logging.Formatter):
    """Formatter para archivo: timestamp ISO + nivel + módulo + mensaje."""

    def format(self, record: logging.LogRecord) -> str:
        ts  = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        lvl = record.levelname
        mod = f"{record.module}.{record.funcName}"[:35]
        msg = record.getMessage()

        base = f"{ts} | {lvl:<8} | {mod:<35} | {msg}"

        # Adjuntar excepción si existe
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configurar(
    nivel_consola: str = "INFO",
    nivel_archivo: str = "DEBUG",
    directorio_logs: str = "logs",
) -> logging.Logger:
    """
    Configura y devuelve el logger raíz del proyecto.
    Llamar una sola vez al inicio de main.py.
    """
    logger = logging.getLogger("mlb")
    if logger.handlers:
        # Ya configurado (ej: doble import en tests)
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Handler de consola ────────────────────────────────────────────────────
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(getattr(logging, nivel_consola.upper(), logging.INFO))
    ch.setFormatter(_ColorFormatter())
    logger.addHandler(ch)

    # ── Handler de archivo con rotación diaria ────────────────────────────────
    os.makedirs(directorio_logs, exist_ok=True)
    hoy       = datetime.now().strftime("%Y-%m-%d")
    log_path  = os.path.join(directorio_logs, f"mlb_{hoy}.log")

    fh = TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",       # rota a medianoche
        interval=1,
        backupCount=30,        # conserva los últimos 30 días
        encoding="utf-8",
    )
    fh.setLevel(getattr(logging, nivel_archivo.upper(), logging.DEBUG))
    fh.setFormatter(_FileFormatter())
    logger.addHandler(fh)

    # Evitar que los mensajes suban al logger raíz de Python
    logger.propagate = False

    logger.info(f"Logger iniciado → {log_path}")
    return logger


def get() -> logging.Logger:
    """Devuelve el logger del proyecto (ya debe estar configurado)."""
    return logging.getLogger("mlb")