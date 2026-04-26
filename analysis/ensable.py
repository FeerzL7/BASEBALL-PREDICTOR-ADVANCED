# analysis/ensemble.py
#
# Modelo Ensemble: Poisson + Regresión Lineal
#
# ── Por qué esto importa ──────────────────────────────────────────────────────
#
# La distribución de Poisson asume equidispersión: E[X] = Var[X].
# En la práctica, equipos "todo o nada" tienen una varianza mucho mayor
# que su media (overdispersión). Ejemplos reales:
#   - Un equipo que anota 0, 0, 1, 10, 0, 9, 0, 1, 8, 0 → media=2.9, var=20.3
#   - Poisson con μ=2.9 subestima la probabilidad de juegos de 8+ carreras
#     y sobreestima la probabilidad de juegos de 2-4 carreras
#
# La regresión lineal sobre los últimos N juegos actúa como segunda señal:
#   - Si la pendiente es positiva → el equipo está en racha ascendente
#   - Si la pendiente es negativa → el equipo está en caída
#   - La predicción de la regresión para el "juego N+1" captura momentum
#
# Combinación adaptativa:
#   μ_ensemble = α(CV) * μ_poisson + [1 - α(CV)] * μ_regresion
#
# Donde α se reduce automáticamente cuando el equipo muestra alta varianza
# (CV = std/mean > CV_UMBRAL), dando más peso a la regresión lineal.
#
# ── Integración en el pipeline ────────────────────────────────────────────────
#
# Se llama DESDE simulation.py, DESPUÉS de proyectar_totales() y ANTES de
# calcular probabilidades Poisson. Solo modifica proj_home y proj_away.
# Todo downstream (value.py, etc.) funciona sin cambios.

import numpy as np
from scipy.stats import linregress
from utils.logger import get as get_log

log = get_log()

# ── Configuración ─────────────────────────────────────────────────────────────

# Número de juegos recientes para la regresión
N_JUEGOS_REGRESION = 10

# Peso base de Poisson cuando el equipo es "normal" (CV bajo)
ALPHA_BASE = 0.70

# Peso mínimo de Poisson cuando el equipo es muy overdispersado (CV alto)
# Si α=0.50, el ensemble da igual peso a Poisson y a la regresión
ALPHA_MIN  = 0.50

# Umbral de CV (coeficiente de variación) para considerar un equipo "todo o nada"
# CV = std / mean. Un equipo consistente tiene CV~0.5; "todo o nada" tiene CV>0.9
CV_UMBRAL_BAJO  = 0.60   # por debajo → α = ALPHA_BASE (Poisson domina)
CV_UMBRAL_ALTO  = 1.00   # por encima → α = ALPHA_MIN  (más peso a regresión)

# Clamp de la proyección ensemble para evitar valores absurdos
PROJ_MIN = 1.5
PROJ_MAX = 12.0

# Mínimo de juegos para ejecutar la regresión (si hay menos, fallback a Poisson)
MIN_JUEGOS_PARA_REGRESION = 5


# ── Funciones internas ────────────────────────────────────────────────────────

def _coef_variacion(runs: list[float]) -> float:
    """
    Calcula el coeficiente de variación (std / mean) de una serie de carreras.
    Mide la dispersión relativa: cuánto varía el equipo respecto a su media.
    Un CV alto indica equipo "todo o nada".
    """
    if len(runs) < 2:
        return 0.0
    arr  = np.array(runs, dtype=float)
    mean = arr.mean()
    if mean < 0.5:
        return 0.0
    return float(arr.std() / mean)


def _alpha_adaptativo(cv: float) -> float:
    """
    Devuelve el peso α de Poisson según el coeficiente de variación.

    - CV <= CV_UMBRAL_BAJO  → α = ALPHA_BASE  (equipo consistente)
    - CV >= CV_UMBRAL_ALTO  → α = ALPHA_MIN   (equipo "todo o nada")
    - Entre los umbrales    → interpolación lineal
    """
    if cv <= CV_UMBRAL_BAJO:
        return ALPHA_BASE
    if cv >= CV_UMBRAL_ALTO:
        return ALPHA_MIN
    # Interpolación lineal entre los dos umbrales
    rango = CV_UMBRAL_ALTO - CV_UMBRAL_BAJO
    t     = (cv - CV_UMBRAL_BAJO) / rango
    return round(ALPHA_BASE + t * (ALPHA_MIN - ALPHA_BASE), 4)


def _proyeccion_regresion(runs: list[float]) -> float | None:
    """
    Ajusta una regresión lineal simple sobre los últimos N juegos y predice
    el valor para el juego siguiente (posición N+1).

    La variable independiente es el índice del juego (0, 1, 2, ..., N-1),
    que captura la tendencia temporal (momentum).

    Retorna None si hay datos insuficientes o la regresión falla.
    """
    if len(runs) < MIN_JUEGOS_PARA_REGRESION:
        return None

    runs_arr = np.array(runs[-N_JUEGOS_REGRESION:], dtype=float)
    x        = np.arange(len(runs_arr), dtype=float)

    try:
        slope, intercept, r_value, p_value, std_err = linregress(x, runs_arr)

        # Predicción para el siguiente juego
        siguiente = float(intercept + slope * len(runs_arr))

        # Clamp: la regresión no puede predecir valores absurdos
        siguiente = max(PROJ_MIN, min(siguiente, PROJ_MAX))

        # Si R² < 0.05, la tendencia es ruido → no confiar en la regresión
        if r_value ** 2 < 0.05:
            return None

        return siguiente

    except Exception as e:
        log.debug(f"Regresión lineal falló: {e}")
        return None


def _obtener_runs_recientes(partido: dict, equipo_key: str) -> list[float]:
    """
    Extrae la serie de carreras recientes de un equipo desde los datos
    disponibles en el partido. Busca en varias fuentes en orden de prioridad:

    1. partido['home_offense']['runs_recientes']  ← si offense.py las guardó
    2. partido['h2h']['runs_home_prom'] como proxy escalar  ← fallback
    3. Lista vacía → no hay datos suficientes
    """
    # Fuente 1: si offense.py guardó la lista de runs recientes del equipo
    offense_key = f"{equipo_key}_offense"
    offense     = partido.get(offense_key, {})
    runs_lista  = offense.get('runs_recientes_lista', [])
    if isinstance(runs_lista, list) and len(runs_lista) >= MIN_JUEGOS_PARA_REGRESION:
        return [float(r) for r in runs_lista]

    # Fuente 2: runs_last_5 como valor escalar (menos info, pero algo es algo)
    # En este caso no podemos hacer regresión con 1 punto → retornar vacío
    return []


def _ensemble_proyeccion(
    mu_poisson: float,
    runs_recientes: list[float],
    nombre_equipo: str,
) -> tuple[float, dict]:
    """
    Combina la proyección Poisson con la regresión lineal.

    Retorna (proj_ensemble, detalle) donde detalle contiene métricas
    para trazabilidad en logs.
    """
    detalle = {
        'mu_poisson':    round(mu_poisson, 3),
        'mu_regresion':  None,
        'alpha':         1.0,
        'cv':            0.0,
        'tipo_equipo':   'sin_datos',
        'proj_ensemble': round(mu_poisson, 3),
    }

    if len(runs_recientes) < MIN_JUEGOS_PARA_REGRESION:
        # Sin datos suficientes → Poisson puro
        detalle['tipo_equipo'] = 'poisson_puro'
        return mu_poisson, detalle

    cv            = _coef_variacion(runs_recientes)
    alpha         = _alpha_adaptativo(cv)
    mu_regresion  = _proyeccion_regresion(runs_recientes)

    detalle['cv']           = round(cv, 3)
    detalle['alpha']        = alpha
    detalle['tipo_equipo']  = (
        'todo_o_nada'  if cv >= CV_UMBRAL_ALTO  else
        'consistente'  if cv <= CV_UMBRAL_BAJO  else
        'moderado'
    )

    if mu_regresion is None:
        # Regresión no significativa → Poisson puro
        detalle['tipo_equipo']   = 'tendencia_plana'
        detalle['proj_ensemble'] = round(mu_poisson, 3)
        return mu_poisson, detalle

    # Ensemble ponderado
    proj_ensemble = alpha * mu_poisson + (1 - alpha) * mu_regresion
    proj_ensemble = max(PROJ_MIN, min(proj_ensemble, PROJ_MAX))
    proj_ensemble = round(proj_ensemble, 3)

    detalle['mu_regresion']  = round(mu_regresion, 3)
    detalle['proj_ensemble'] = proj_ensemble

    log.debug(
        f"  Ensemble {nombre_equipo}: "
        f"CV={cv:.2f} α={alpha} tipo={detalle['tipo_equipo']} | "
        f"Poisson={mu_poisson:.2f} Regr={mu_regresion:.2f} "
        f"→ Ensemble={proj_ensemble:.2f}"
    )

    return proj_ensemble, detalle


# ── Punto de entrada público ──────────────────────────────────────────────────

def ajustar_proyecciones_ensemble(partidos: list) -> list:
    """
    Ajusta proj_home y proj_away de cada partido combinando la proyección
    Poisson (ya calculada por projections.py) con una regresión lineal
    sobre las carreras recientes del equipo.

    Guarda los detalles del ensemble en partido['ensemble_home'] y
    partido['ensemble_away'] para trazabilidad en logs y CSV.

    Si los datos de carreras recientes no están disponibles para un equipo,
    el partido mantiene su proyección Poisson original sin cambios.

    Llamar DESDE simulation.py, justo antes de simular probabilidades.
    """
    ajustados = 0

    for partido in partidos:
        home      = partido.get('home_team', '?')
        away      = partido.get('away_team', '?')
        proj_home = partido.get('proj_home', 4.5)
        proj_away = partido.get('proj_away', 4.5)

        runs_home = _obtener_runs_recientes(partido, 'home')
        runs_away = _obtener_runs_recientes(partido, 'away')

        proj_home_adj, det_home = _ensemble_proyeccion(proj_home, runs_home, home)
        proj_away_adj, det_away = _ensemble_proyeccion(proj_away, runs_away, away)

        # Solo actualizar si el ensemble cambió algo
        cambio_home = abs(proj_home_adj - proj_home) > 0.001
        cambio_away = abs(proj_away_adj - proj_away) > 0.001

        if cambio_home or cambio_away:
            ajustados += 1

        partido['proj_home']       = proj_home_adj
        partido['proj_away']       = proj_away_adj
        partido['proj_total']      = round(proj_home_adj + proj_away_adj, 3)
        partido['ensemble_home']   = det_home
        partido['ensemble_away']   = det_away

    if ajustados > 0:
        log.debug(f"Ensemble: {ajustados}/{len(partidos)} partidos con proyección ajustada.")
    else:
        log.debug("Ensemble: sin datos de carreras recientes → Poisson puro en todos los partidos.")

    return partidos


# ── Utilidad: alimentar la lista de runs desde offense.py ────────────────────
#
# Para que el ensemble funcione con datos reales, offense.py necesita guardar
# la lista completa de carreras recientes, no solo el promedio.
# Esta función puede llamarse desde offense.py para transformar el dato.

def preparar_runs_lista(runs_raw) -> list[float]:
    """
    Normaliza una lista de runs recientes a formato list[float].
    Acepta lista, numpy array, o escalar (en cuyo caso retorna lista vacía).
    """
    if isinstance(runs_raw, (list, tuple, np.ndarray)):
        return [float(r) for r in runs_raw if r is not None]
    return []