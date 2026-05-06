# Analisis FODA y estabilizacion del modelo

## Fortalezas

- Pipeline modular: pitching, ofensiva, defensiva, contexto, mercado, value, tracking y backtesting estan separados.
- Usa senales relevantes para MLB: abridores, bullpen, park factors, clima, H2H, cuotas y movimiento de linea.
- Ya existe tracking de ROI y backtesting, lo que permite tomar decisiones con evidencia.
- El mercado TOTAL muestra mejor comportamiento historico que ML/RL en la muestra local.

## Oportunidades

- Calibrar probabilidades contra la probabilidad implicita del mercado para reducir sobreconfianza.
- Usar el backtesting para activar/desactivar mercados segun evidencia, no por intuicion.
- Mejorar gestion de riesgo: menos picks, menor stake, limite de exposicion diaria y bloqueo por movimiento contrario.
- Separar diagnostico de picks activos: ML/RL pueden seguir calculandose sin arriesgar bankroll.

## Debilidades

- ML y RL presentan ROI negativo en el backtest local disponible.
- Las probabilidades historicas salian demasiado altas, generando EV inflado y stakes agresivos.
- El ensemble estaba desactivado por un typo de archivo (`ensable.py` vs `ensemble.py`).
- El calibrador de backtesting apuntaba a constantes antiguas (`UMBRAL_VALOR_*`) que no existen en `value.py`.
- La API key estaba acoplada al codigo fuente.

## Amenazas

- La varianza natural de MLB es alta: bullpen, lesiones, lineups tardios y extra innings pueden romper picks buenos.
- El mercado puede corregir antes de que el modelo capture informacion nueva.
- Muestras pequenas pueden sobreoptimizar umbrales.
- Ningun modelo puede garantizar ganancias; solo puede mejorar esperanza, disciplina y control de drawdown.

## Cambios implementados

- Ensemble activado al corregir `analysis/ensemble.py`.
- ML/RL pasan a modo observacion por ROI negativo historico; TOTAL queda activo.
- Probabilidades calibradas con shrink hacia el mercado y caps superiores para evitar EV irreal.
- Kelly fraccionado reducido y stake maximo por pick bajado.
- Gestion de riesgo diaria: maximo 3 picks, 3% de exposicion total, 1% por pick y descarte si el movimiento contradice.
- Backtesting evita recomendar umbrales de mercados con ROI negativo.
- Odds API ahora usa `.env`/variable de entorno y timeout HTTP.
