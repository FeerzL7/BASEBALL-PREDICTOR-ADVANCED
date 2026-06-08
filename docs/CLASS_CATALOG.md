# Catalogo de clases

El repositorio usa pocas clases; la mayor parte del sistema es procedural con diccionarios mutables.

## `bankroll.staking.StakingStrategy`

- Archivo: `bankroll/staking.py:7`.
- Tipo: `Protocol`.
- Responsabilidad: interfaz para estrategias de staking. Permite sustituir el modelo de stake sin cambiar `aplicar_staking_dinamico`.
- Metodos:
  - `stake_pct(self, partido) -> int`: debe devolver stake entero en porcentaje.
- Atributos: ninguno definido.
- Dependencias: `typing.Protocol`.
- Relaciones: implementada de forma estructural por `IntegerPercentStaking`.

## `bankroll.staking.IntegerPercentStaking`

- Archivo: `bankroll/staking.py:54`.
- Tipo: `dataclass`.
- Responsabilidad: modelo conservador de staking en porcentajes enteros.
- Atributos:
  - `min_pct`: default `MIN_STAKE_PCT`.
  - `max_pct`: default `MAX_STAKE_PCT`.
- Metodos:
  - `stake_pct(self, partido) -> int`: identifica mercado del `mejor_pick`, verifica stake base aprobado por `value.py`, evalua EV/probabilidad/movimiento, reduce por `data_quality_flags` y limita entre min/max.
- Dependencias:
  - `bankroll.config.MIN_STAKE_PCT`, `MAX_STAKE_PCT`.
  - Helpers `mercado_mejor_pick`, `stake_key`, `valor_key`, `probabilidad_pick`.
- Relaciones:
  - Usada por `aplicar_staking_dinamico`.
  - Opera despues de `analysis.value` y antes de `utils.risk_management`.

## `utils.logger._ColorFormatter`

- Archivo: `utils/logger.py:34`.
- Tipo: subclase de `logging.Formatter`.
- Responsabilidad: formato de consola con colores ANSI por nivel.
- Atributos:
  - `FMT`: mapa nivel -> color.
- Metodos:
  - `format(self, record) -> str`: devuelve linea coloreada con hora, nivel y mensaje.
- Dependencias: `logging`.
- Relaciones: instanciada por `configurar` para el handler de consola.

## `utils.logger._FileFormatter`

- Archivo: `utils/logger.py:50`.
- Tipo: subclase de `logging.Formatter`.
- Responsabilidad: formato de archivo con timestamp ISO, nivel, modulo y mensaje.
- Atributos: usa `formatException` heredado.
- Metodos:
  - `format(self, record) -> str`: construye linea estable para logs persistentes.
- Dependencias: `logging`, `datetime`.
- Relaciones: instanciada por `configurar` para `TimedRotatingFileHandler`.

## Clases externas usadas

- `pandas.DataFrame` en `main.py` y dashboard.
- `plotly.graph_objects.Figure`, `go.Scatter`, `go.Bar` en dashboard.
- `logging.handlers.TimedRotatingFileHandler` en logger.

No se detectaron clases de dominio como `Game`, `Pick`, `Market`, `Bankroll` o `Projection`; esos conceptos estan representados por diccionarios y filas CSV.
