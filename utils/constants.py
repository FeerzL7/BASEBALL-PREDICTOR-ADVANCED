# utils/constants.py
from datetime import datetime

API_KEY = "e16bac9cd9c31a572916a8b86087018f"
SPORT   = "baseball_mlb"
REGION  = "us"
MARKETS = "h2h,totals,spreads"
TODAY   = datetime.now().strftime('%Y-%m-%d')

# Valores históricos de park factor por estadio.
# Se usan como FALLBACK cuando la API no tiene suficientes juegos
# en la temporada actual. La fuente dinámica vive en analysis/park_factors.py.
PARK_FACTORS = {
    'Coors Field':              1.34,
    'Fenway Park':              1.12,
    'Globe Life Field':         1.10,
    'Great American Ball Park': 1.08,
    'Minute Maid Park':         1.06,
    'Wrigley Field':            1.05,
    'Yankee Stadium':           1.04,
    'Truist Park':              1.03,
    'Chase Field':              1.02,
    'Dodger Stadium':           1.01,
    'Citizens Bank Park':       1.01,
    'Angel Stadium':            1.00,
    'Kauffman Stadium':         0.99,
    'Target Field':             0.98,
    'Rogers Centre':            0.98,
    'Busch Stadium':            0.97,
    'Progressive Field':        0.97,
    'American Family Field':    0.96,
    'Nationals Park':           0.96,
    'Citi Field':               0.95,
    'Camden Yards':             0.95,
    'T-Mobile Park':            0.94,
    'PNC Park':                 0.94,
    'Oakland Coliseum':         0.94,
    'Comerica Park':            0.93,
    'Oracle Park':              0.93,
    'loanDepot park':           0.92,
    'Guaranteed Rate Field':    0.92,
    'Tropicana Field':          0.91,
    'default':                  1.0,
}