import os

ROI_FILE = "output/roi_tracking.csv"
BANKROLL_HISTORY_FILE = "output/bankroll_history.csv"
MONTHLY_STATS_FILE = "output/bankroll_monthly_stats.csv"

INITIAL_BANKROLL = float(os.getenv("INITIAL_BANKROLL", "1000"))

MIN_STAKE_PCT = int(os.getenv("MIN_STAKE_PCT", "1"))
MAX_STAKE_PCT = int(os.getenv("MAX_STAKE_PCT", "3"))
MAX_DAILY_EXPOSURE_PCT = int(os.getenv("MAX_DAILY_EXPOSURE_PCT", "6"))

