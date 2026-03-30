# ⚾ MLB Predictor Advanced

Sistema profesional de análisis y predicción diaria para partidos de MLB, basado en simulaciones estadísticas, lógica de apuestas con valor esperado, y registro automatizado de rendimiento.

---

## 📁 Estructura del Proyecto

mlb-predictor-advanced/
├── analysis/
│ ├── pitching.py # Análisis de abridores
│ ├── offense.py # Análisis ofensivo por equipo
│ ├── defense.py # Análisis defensivo
│ ├── projections.py # Proyecciones de carreras
│ ├── simulation.py # Simulaciones Poisson (probabilidades, Kelly, RL)
│ ├── h2h.py # Historial entre equipos (H2H)
│ ├── value.py # Cálculo de picks, valor y mejor apuesta
│ └── markets.py # Asociación de cuotas desde API
├── data/
│ └── odds_api.py # Conexión a The Odds API
├── tracking/
│ └── roi_tracker.py # Registro de picks y cálculo de ROI
├── utils/
│ └── constants.py # Claves, parámetros, factores de parque, fecha
├── output/
│ └── ... # CSVs de picks y ROI
├── main.py # Script principal (flujo completo de análisis)
└── README.md # Documentación del sistema


---

## ⚙️ Flujo de Análisis (`main.py`)

1. **Carga de datos de partidos (abridores):**
   - `analysis/pitching.py`: Extrae estadísticas clave de lanzadores usando `statsapi`.

2. **Análisis ofensivo:**
   - `analysis/offense.py`: Calcula OPS, wRC+ y producción ofensiva reciente.

3. **Análisis defensivo:**
   - `analysis/defense.py`: Calcula errores, doble plays y fielding %.

4. **Proyecciones de carreras esperadas:**
   - `analysis/projections.py`: Usa producción ofensiva, ERA rival y Park Factor.

5. **Simulaciones Poisson:**
   - `analysis/simulation.py`: Simula probabilidades de victoria y cubrir el runline.

6. **Análisis Head-to-Head:**
   - `analysis/h2h.py`: Historial reciente entre ambos equipos.

7. **Obtención de cuotas (Odds API):**
   - `data/odds_api.py`: Llama a The Odds API con API Key.
   - `analysis/markets.py`: Asocia correctamente las cuotas al partido analizado.

8. **Análisis de valor y generación de picks:**
   - `analysis/value.py`: Calcula valor esperado (EV), Kelly, selecciona mejor pick.

9. **Exportación y logging:**
   - `output/predicciones_YYYY-MM-DD.csv`: Picks diarios.
   - `tracking/roi_tracker.py`: Guarda resultados y calcula ROI acumulado.

---

## 📌 Lógica de Valor (EV y Kelly)

- Simulación Poisson estima probabilidades de ganar (ML) y cubrir spread (RL).
- Se calcula el **valor esperado** de cada cuota y se usa **criterio de Kelly** moderado para stake sugerido.
- Se selecciona el **mejor pick** por partido si cumple con umbrales de valor mínimo y probabilidad mínima.

---

## 🧠 Variables Clave (`constants.py`)

```python
API_KEY = "..."             # Clave de The Odds API
SPORT = "baseball_mlb"
REGION = "us"
MARKETS = "h2h,totals,spreads"
PARK_FACTORS = { ... }      # Ajuste de carreras por estadio
TODAY = datetime.now().strftime('%Y-%m-%d')
🧾 Output Generado
output/predicciones_YYYY-MM-DD.csv: Picks con todas las métricas de análisis.

output/roi_tracking.csv: Historial de apuestas con ganancia/pérdida y cálculo automático de ROI.

📈 ROI Tracking Automático
Cada pick generado es registrado automáticamente como “pendiente”. Posteriormente puedes actualizar los resultados (“win” o “lose”) manualmente en el archivo roi_tracking.csv. El ROI se recalcula al finalizar cada análisis.

🛠️ Requisitos
Python 3.10 o superior

Paquetes:

bash
Copiar
Editar
pip install statsapi requests pandas scipy numpy
✅ Ejecución
bash
Copiar
Editar
python main.py
💡 Ideas Futuras
Módulo de backtesting histórico.

Dashboard de resultados.

Integración con Telegram/Discord para alertas automáticas.

Soporte para múltiples casas de apuestas.

Evaluación automática de picks (web scraping de resultados).

🧠 Autor y Mantenimiento
Desarrollado por Fernando Jesus Castillo Ramirez como parte de un sistema avanzado de apuestas MLB para maximizar valor esperado y ROI mediante análisis cuantitativo, simulaciones y principios de gestión de riesgo.
