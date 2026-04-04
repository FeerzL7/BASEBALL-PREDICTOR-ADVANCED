# dashboard/roi_dashboard.py
#
# Ejecutar desde la raíz del proyecto:
#   streamlit run dashboard/roi_dashboard.py
#
# Requiere: streamlit, plotly, pandas
#   pip install streamlit plotly pandas

import sys
import os

# Permitir imports desde la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime, timedelta

# ── Configuración de página ────────────────────────────────────────────────────
st.set_page_config(
    page_title="MLB Predictor — ROI Dashboard",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Estilos ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }

  .main { background: #0d0f14; }

  .metric-card {
    background: #13161d;
    border: 1px solid #1e222e;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    text-align: center;
  }
  .metric-label {
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #4a5168;
    margin-bottom: 6px;
    font-family: 'DM Mono', monospace;
  }
  .metric-value {
    font-size: 28px;
    font-weight: 600;
    font-family: 'DM Mono', monospace;
    line-height: 1;
  }
  .metric-sub {
    font-size: 12px;
    color: #4a5168;
    margin-top: 4px;
    font-family: 'DM Mono', monospace;
  }
  .positive { color: #4ade80; }
  .negative { color: #f87171; }
  .neutral  { color: #94a3b8; }
  .accent   { color: #60a5fa; }

  .section-title {
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #4a5168;
    font-family: 'DM Mono', monospace;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #1e222e;
  }

  .pick-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #1a1d26;
    font-size: 13px;
  }
  .pick-win  { color: #4ade80; font-family: 'DM Mono', monospace; font-size: 11px; }
  .pick-lose { color: #f87171; font-family: 'DM Mono', monospace; font-size: 11px; }
  .pick-pend { color: #60a5fa; font-family: 'DM Mono', monospace; font-size: 11px; }

  div[data-testid="stSidebar"] {
    background: #0d0f14;
    border-right: 1px solid #1e222e;
  }

  h1 { font-family: 'DM Sans', sans-serif !important; font-weight: 300 !important; }
  h2, h3 { font-family: 'DM Sans', sans-serif !important; font-weight: 500 !important; }
</style>
""", unsafe_allow_html=True)

# ── Carga de datos ─────────────────────────────────────────────────────────────
ROI_FILE = "output/roi_tracking.csv"
PRED_DIR = "output"

@st.cache_data(ttl=60)
def cargar_roi() -> pd.DataFrame:
    if not os.path.exists(ROI_FILE):
        return pd.DataFrame()
    df = pd.read_csv(ROI_FILE, encoding='utf-8-sig')
    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
    df['cuota']      = pd.to_numeric(df['cuota'],      errors='coerce')
    df['ganancia']   = pd.to_numeric(df['ganancia'],   errors='coerce')
    df['valor']      = pd.to_numeric(df['valor'],      errors='coerce')
    df['probabilidad'] = pd.to_numeric(df['probabilidad'], errors='coerce')
    return df.sort_values('fecha')


@st.cache_data(ttl=60)
def cargar_predicciones() -> pd.DataFrame:
    """Lee todos los CSVs de predicciones y los concatena."""
    import glob
    archivos = glob.glob(os.path.join(PRED_DIR, "predicciones_*.csv"))
    if not archivos:
        return pd.DataFrame()
    dfs = []
    for f in archivos:
        try:
            dfs.append(pd.read_csv(f, encoding='utf-8-sig'))
        except Exception:
            pass
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    if 'start_time' in df.columns:
        df['fecha'] = pd.to_datetime(df['start_time'], errors='coerce').dt.date
    return df


def color_roi(v: float) -> str:
    if v > 0:   return "positive"
    if v < 0:   return "negative"
    return "neutral"


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚾ MLB Predictor")
    st.markdown("---")

    df_raw = cargar_roi()

    if df_raw.empty:
        st.warning("No hay datos en roi_tracking.csv")
        st.stop()

    resueltos = df_raw[df_raw['resultado'].isin(['win', 'lose'])]
    pendientes = df_raw[df_raw['resultado'] == 'pendiente']

    st.markdown("**Filtros**")

    mercados_disp = ['Todos'] + sorted(df_raw['mercado'].dropna().unique().tolist())
    mercado_sel   = st.selectbox("Mercado", mercados_disp)

    fecha_min = df_raw['fecha'].min().date() if not df_raw.empty else datetime.today().date()
    fecha_max = df_raw['fecha'].max().date() if not df_raw.empty else datetime.today().date()

    rango = st.date_input(
        "Rango de fechas",
        value=(fecha_min, fecha_max),
        min_value=fecha_min,
        max_value=fecha_max,
    )

    solo_resueltos = st.checkbox("Solo picks resueltos", value=True)

    ventana_rolling = st.slider("Ventana rolling (picks)", 5, 50, 20, step=5)

    st.markdown("---")
    st.markdown(f"<span style='color:#4a5168;font-size:12px;font-family:DM Mono'>Total picks: {len(df_raw)}<br>Resueltos: {len(resueltos)}<br>Pendientes: {len(pendientes)}</span>", unsafe_allow_html=True)


# ── Aplicar filtros ────────────────────────────────────────────────────────────
df = df_raw.copy()

if len(rango) == 2:
    df = df[(df['fecha'].dt.date >= rango[0]) & (df['fecha'].dt.date <= rango[1])]

if mercado_sel != 'Todos':
    df = df[df['mercado'] == mercado_sel]

if solo_resueltos:
    df = df[df['resultado'].isin(['win', 'lose'])]

if df.empty:
    st.warning("Sin datos para los filtros seleccionados.")
    st.stop()

# ── Métricas calculadas ────────────────────────────────────────────────────────
total   = len(df)
wins    = (df['resultado'] == 'win').sum()
losses  = (df['resultado'] == 'lose').sum()
pend    = (df['resultado'] == 'pendiente').sum()
hit_rate = wins / (wins + losses) * 100 if (wins + losses) > 0 else 0
ganancia_total = df['ganancia'].sum()
roi_total = ganancia_total / total * 100 if total > 0 else 0
cuota_media = df['cuota'].mean()
ev_medio = df['valor'].mean() if 'valor' in df.columns else 0
racha_actual = 0
for r in df.sort_values('fecha')['resultado'].tolist()[::-1]:
    if r == 'win':  racha_actual += 1
    elif r == 'lose': break

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='color:#e2e8f0;font-size:26px;font-weight:300;margin-bottom:4px'>"
    f"ROI Dashboard</h1>"
    f"<p style='color:#4a5168;font-size:13px;font-family:DM Mono;margin-top:0'>"
    f"MLB Predictor Advanced &nbsp;·&nbsp; "
    f"{rango[0].strftime('%b %d') if len(rango)==2 else '—'} → "
    f"{rango[1].strftime('%b %d, %Y') if len(rango)==2 else '—'}"
    f"</p>",
    unsafe_allow_html=True
)

# ── Tarjetas de métricas ───────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)

def metric_card(col, label, value, sub="", cls="neutral"):
    col.markdown(
        f"<div class='metric-card'>"
        f"<div class='metric-label'>{label}</div>"
        f"<div class='metric-value {cls}'>{value}</div>"
        f"<div class='metric-sub'>{sub}</div>"
        f"</div>",
        unsafe_allow_html=True
    )

metric_card(c1, "ROI",        f"{roi_total:+.1f}%",   f"{total} picks",        color_roi(roi_total))
metric_card(c2, "Hit rate",   f"{hit_rate:.1f}%",     f"{wins}W / {losses}L",  "accent")
metric_card(c3, "Ganancia",   f"{ganancia_total:+.2f}u", "unidades",           color_roi(ganancia_total))
metric_card(c4, "Cuota media",f"{cuota_media:.2f}",   "decimal",               "neutral")
metric_card(c5, "EV medio",   f"{ev_medio:.1f}",      "valor esperado",        "neutral")
metric_card(c6, "Racha",      f"+{racha_actual}",     "wins consecutivos",      "positive" if racha_actual > 0 else "neutral")

st.markdown("<br>", unsafe_allow_html=True)

# ── Gráficas ────────────────────────────────────────────────────────────────────
col_izq, col_der = st.columns([3, 2], gap="large")

# ── Curva de bankroll acumulado ────────────────────────────────────────────────
with col_izq:
    st.markdown("<div class='section-title'>Bankroll acumulado</div>", unsafe_allow_html=True)

    df_sorted = df[df['resultado'].isin(['win','lose'])].sort_values('fecha').copy()
    df_sorted['acumulado'] = df_sorted['ganancia'].cumsum()
    df_sorted['pick_num']  = range(1, len(df_sorted) + 1)

    # Rolling ROI
    df_sorted['rolling_ganancia'] = df_sorted['ganancia'].rolling(ventana_rolling, min_periods=1).mean() * 100

    fig_bank = go.Figure()

    # Área de ganancia
    fig_bank.add_trace(go.Scatter(
        x=df_sorted['pick_num'], y=df_sorted['acumulado'],
        fill='tozeroy',
        fillcolor='rgba(74,222,128,0.06)',
        line=dict(color='#4ade80', width=2),
        name='Bankroll',
        hovertemplate='Pick %{x}<br>Acumulado: %{y:.2f}u<extra></extra>',
    ))

    # Línea de break-even
    fig_bank.add_hline(y=0, line_dash='dot', line_color='#1e222e', line_width=1)

    # Puntos win/lose
    wins_df  = df_sorted[df_sorted['resultado'] == 'win']
    loses_df = df_sorted[df_sorted['resultado'] == 'lose']

    fig_bank.add_trace(go.Scatter(
        x=wins_df['pick_num'], y=wins_df['acumulado'],
        mode='markers',
        marker=dict(color='#4ade80', size=5, symbol='circle'),
        name='Win',
        hovertemplate='WIN %{x}<extra></extra>',
    ))
    fig_bank.add_trace(go.Scatter(
        x=loses_df['pick_num'], y=loses_df['acumulado'],
        mode='markers',
        marker=dict(color='#f87171', size=5, symbol='circle'),
        name='Lose',
        hovertemplate='LOSE %{x}<extra></extra>',
    ))

    fig_bank.update_layout(
        plot_bgcolor='#13161d', paper_bgcolor='#13161d',
        font=dict(family='DM Mono', color='#4a5168', size=11),
        margin=dict(l=0, r=0, t=0, b=0),
        height=260,
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, title='Picks',
                   title_font=dict(size=10), tickfont=dict(size=10)),
        yaxis=dict(showgrid=True, gridcolor='#1a1d26', zeroline=False,
                   title='Unidades', title_font=dict(size=10), tickfont=dict(size=10)),
        hovermode='x unified',
    )
    st.plotly_chart(fig_bank, use_container_width=True)

# ── Hit rate por mercado ───────────────────────────────────────────────────────
with col_der:
    st.markdown("<div class='section-title'>Hit rate por mercado</div>", unsafe_allow_html=True)

    stats_mercado = (
        df[df['resultado'].isin(['win','lose'])]
        .groupby('mercado')
        .agg(
            picks=('resultado','count'),
            wins=('resultado', lambda x: (x=='win').sum()),
        )
        .reset_index()
    )
    stats_mercado['hit_rate'] = stats_mercado['wins'] / stats_mercado['picks'] * 100
    stats_mercado['roi'] = stats_mercado.apply(
        lambda r: df[(df['mercado']==r['mercado']) & df['resultado'].isin(['win','lose'])]['ganancia'].sum() / r['picks'] * 100,
        axis=1
    )

    colors = ['#4ade80' if r > 0 else '#f87171' for r in stats_mercado['roi']]

    fig_mer = go.Figure()
    fig_mer.add_trace(go.Bar(
        x=stats_mercado['mercado'],
        y=stats_mercado['hit_rate'],
        marker_color=colors,
        text=[f"{v:.0f}%" for v in stats_mercado['hit_rate']],
        textposition='outside',
        textfont=dict(family='DM Mono', size=11, color='#94a3b8'),
        hovertemplate='%{x}<br>Hit rate: %{y:.1f}%<extra></extra>',
        name='Hit rate',
    ))
    fig_mer.add_hline(y=52.4, line_dash='dot', line_color='#60a5fa',
                      annotation_text='breakeven ~52.4%',
                      annotation_font=dict(size=9, color='#60a5fa'))

    fig_mer.update_layout(
        plot_bgcolor='#13161d', paper_bgcolor='#13161d',
        font=dict(family='DM Mono', color='#4a5168', size=11),
        margin=dict(l=0, r=0, t=0, b=0),
        height=260,
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='#1a1d26', zeroline=False,
                   range=[0, 100], ticksuffix='%'),
    )
    st.plotly_chart(fig_mer, use_container_width=True)

# ── Segunda fila ───────────────────────────────────────────────────────────────
col_a, col_b, col_c = st.columns([2, 2, 2], gap="large")

# ── ROI rolling ───────────────────────────────────────────────────────────────
with col_a:
    st.markdown(f"<div class='section-title'>ROI rolling ({ventana_rolling} picks)</div>", unsafe_allow_html=True)

    fig_roll = go.Figure()
    fig_roll.add_trace(go.Scatter(
        x=df_sorted['pick_num'],
        y=df_sorted['rolling_ganancia'],
        line=dict(color='#60a5fa', width=2),
        fill='tozeroy',
        fillcolor='rgba(96,165,250,0.07)',
        hovertemplate='Pick %{x}<br>ROI rolling: %{y:.1f}%<extra></extra>',
    ))
    fig_roll.add_hline(y=0, line_dash='dot', line_color='#1e222e', line_width=1)
    fig_roll.update_layout(
        plot_bgcolor='#13161d', paper_bgcolor='#13161d',
        font=dict(family='DM Mono', color='#4a5168', size=11),
        margin=dict(l=0, r=0, t=0, b=0),
        height=220, showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='#1a1d26', zeroline=False, ticksuffix='%'),
    )
    st.plotly_chart(fig_roll, use_container_width=True)

# ── Distribución de EV ────────────────────────────────────────────────────────
with col_b:
    st.markdown("<div class='section-title'>EV vs resultado</div>", unsafe_allow_html=True)

    df_ev = df[df['resultado'].isin(['win','lose']) & df['valor'].notna()].copy()
    df_ev['color'] = df_ev['resultado'].map({'win': '#4ade80', 'lose': '#f87171'})

    fig_ev = go.Figure()
    for resultado, color in [('win','#4ade80'), ('lose','#f87171')]:
        sub = df_ev[df_ev['resultado'] == resultado]
        fig_ev.add_trace(go.Histogram(
            x=sub['valor'],
            name=resultado.upper(),
            marker_color=color,
            opacity=0.75,
            nbinsx=15,
            hovertemplate=f'{resultado.upper()}: %{{x:.0f}} EV<br>N=%{{y}}<extra></extra>',
        ))
    fig_ev.update_layout(
        barmode='overlay',
        plot_bgcolor='#13161d', paper_bgcolor='#13161d',
        font=dict(family='DM Mono', color='#4a5168', size=11),
        margin=dict(l=0, r=0, t=0, b=0),
        height=220,
        legend=dict(font=dict(size=10, color='#94a3b8'),
                    bgcolor='#13161d', bordercolor='#1e222e'),
        xaxis=dict(showgrid=False, zeroline=False, title='EV'),
        yaxis=dict(showgrid=True, gridcolor='#1a1d26', zeroline=False),
    )
    st.plotly_chart(fig_ev, use_container_width=True)

# ── Rendimiento por cuota ──────────────────────────────────────────────────────
with col_c:
    st.markdown("<div class='section-title'>Hit rate por cuota</div>", unsafe_allow_html=True)

    df_cuota = df[df['resultado'].isin(['win','lose']) & df['cuota'].notna()].copy()
    df_cuota['rango_cuota'] = pd.cut(
        df_cuota['cuota'],
        bins=[1.0, 1.5, 1.7, 1.9, 2.1, 2.5, 10.0],
        labels=['1.0-1.5', '1.5-1.7', '1.7-1.9', '1.9-2.1', '2.1-2.5', '>2.5'],
    )
    agg_cuota = (
        df_cuota.groupby('rango_cuota', observed=True)
        .agg(picks=('resultado','count'), wins=('resultado', lambda x:(x=='win').sum()))
        .reset_index()
    )
    agg_cuota['hit_rate'] = agg_cuota['wins'] / agg_cuota['picks'] * 100

    fig_cq = go.Figure(go.Bar(
        x=agg_cuota['rango_cuota'].astype(str),
        y=agg_cuota['hit_rate'],
        marker_color='#a78bfa',
        text=[f"{v:.0f}%<br>n={n}" for v, n in zip(agg_cuota['hit_rate'], agg_cuota['picks'])],
        textposition='outside',
        textfont=dict(family='DM Mono', size=10, color='#94a3b8'),
        hovertemplate='%{x}<br>Hit rate: %{y:.1f}%<extra></extra>',
    ))
    fig_cq.add_hline(y=52.4, line_dash='dot', line_color='#60a5fa', line_width=1)
    fig_cq.update_layout(
        plot_bgcolor='#13161d', paper_bgcolor='#13161d',
        font=dict(family='DM Mono', color='#4a5168', size=11),
        margin=dict(l=0, r=0, t=0, b=0),
        height=220, showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, title='Rango cuota'),
        yaxis=dict(showgrid=True, gridcolor='#1a1d26', zeroline=False,
                   range=[0, 110], ticksuffix='%'),
    )
    st.plotly_chart(fig_cq, use_container_width=True)

# ── Tabla de picks recientes ───────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Picks recientes</div>", unsafe_allow_html=True)

df_tabla = df.sort_values('fecha', ascending=False).head(30).copy()

def badge_resultado(r):
    if r == 'win':      return '🟢 WIN'
    if r == 'lose':     return '🔴 LOSE'
    return '🔵 PEND'

def fmt_ganancia(g):
    if pd.isna(g): return '—'
    return f"+{g:.2f}u" if g > 0 else f"{g:.2f}u"

df_tabla['Resultado'] = df_tabla['resultado'].map({
    'win': '🟢 WIN', 'lose': '🔴 LOSE', 'pendiente': '🔵 PEND', 'null': '⬜ PUSH',
})
df_tabla['Ganancia'] = df_tabla['ganancia'].apply(fmt_ganancia)
df_tabla['Fecha']    = df_tabla['fecha'].dt.strftime('%b %d')

st.dataframe(
    df_tabla[['Fecha','juego','mercado','seleccion','cuota','valor','Resultado','Ganancia']]
    .rename(columns={
        'juego': 'Partido', 'mercado': 'Mercado',
        'seleccion': 'Pick', 'cuota': 'Cuota', 'valor': 'EV',
    }),
    use_container_width=True,
    hide_index=True,
    column_config={
        'Cuota': st.column_config.NumberColumn(format="%.2f"),
        'EV':    st.column_config.NumberColumn(format="%.1f"),
    }
)

# ── Tabla resumen por mercado ──────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>Resumen por mercado</div>", unsafe_allow_html=True)

col_t1, col_t2 = st.columns([1, 2])

with col_t1:
    st.dataframe(
        stats_mercado.rename(columns={
            'mercado': 'Mercado', 'picks': 'Picks',
            'wins': 'Wins', 'hit_rate': 'Hit%', 'roi': 'ROI%',
        }).style.format({'Hit%': '{:.1f}', 'ROI%': '{:.1f}'}),
        use_container_width=True,
        hide_index=True,
    )

with col_t2:
    # Evolución hit rate rolling por mercado
    st.markdown("<div class='section-title' style='font-size:10px'>Hit rate rolling por mercado</div>", unsafe_allow_html=True)

    df_roll_m = df[df['resultado'].isin(['win','lose'])].copy().sort_values('fecha')
    fig_rm = go.Figure()
    colores_mercado = {'ML': '#4ade80', 'RL': '#60a5fa', 'TOTAL': '#a78bfa'}

    for mercado in df_roll_m['mercado'].unique():
        sub = df_roll_m[df_roll_m['mercado'] == mercado].copy()
        sub['rolling_hr'] = (sub['resultado'] == 'win').rolling(
            min(ventana_rolling, len(sub)), min_periods=1).mean() * 100
        sub['pick_num'] = range(1, len(sub)+1)
        color = colores_mercado.get(mercado, '#94a3b8')
        fig_rm.add_trace(go.Scatter(
            x=sub['pick_num'], y=sub['rolling_hr'],
            name=mercado, line=dict(color=color, width=2),
            hovertemplate=f'{mercado}: %{{y:.1f}}%<extra></extra>',
        ))

    fig_rm.add_hline(y=52.4, line_dash='dot', line_color='#1e222e', line_width=1)
    fig_rm.update_layout(
        plot_bgcolor='#13161d', paper_bgcolor='#13161d',
        font=dict(family='DM Mono', color='#4a5168', size=11),
        margin=dict(l=0, r=0, t=0, b=0),
        height=200,
        legend=dict(font=dict(size=10, color='#94a3b8'),
                    bgcolor='#13161d', orientation='h',
                    yanchor='bottom', y=1.0, xanchor='left', x=0),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='#1a1d26', zeroline=False, ticksuffix='%'),
    )
    st.plotly_chart(fig_rm, use_container_width=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f"<p style='text-align:center;color:#2a2d3a;font-size:11px;font-family:DM Mono'>"
    f"MLB Predictor Advanced &nbsp;·&nbsp; "
    f"actualizado {datetime.now().strftime('%H:%M:%S')}"
    f"</p>",
    unsafe_allow_html=True
)