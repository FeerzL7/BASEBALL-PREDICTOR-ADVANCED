from datetime import datetime

API_KEY = "e16bac9cd9c31a572916a8b86087018f"
SPORT = "baseball_mlb"
REGION = "us"
MARKETS = "h2h,totals,spreads"
TODAY = datetime.now().strftime('%Y-%m-%d')

PARK_FACTORS = {
    'Coors Field': 1.34,
    'Fenway Park': 1.12,
    'Globe Life Field': 1.10,
    'Oakland Coliseum': 0.94,
    'Dodger Stadium': 1.01,
    'Petco Park': 0.92,
    'default': 1.0
}
