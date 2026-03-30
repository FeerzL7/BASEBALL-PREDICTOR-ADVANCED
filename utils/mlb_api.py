# utils/mlb_api.py
from statsapi import lookup_team, get
from datetime import datetime
import numpy as np

def get_team_stats_vs_pitch_hand(team_name, vs_hand='R'):
    try:
        team_id = lookup_team(team_name)[0]['id']
        stats = get(f"teams/{team_id}/stats", params={"group": "hitting", "season": datetime.now().year})["stats"]
        statline = stats[0]["splits"][0]["stat"]

        game_logs = get(f"teams/{team_id}/stats/game/season", params={"season": datetime.now().year})["stats"][0]["splits"]
        recent_games = game_logs[-5:] if len(game_logs) >= 5 else game_logs
        runs_last_5 = np.mean([int(g["stat"].get("runs", 4)) for g in recent_games]) if recent_games else 4.5

        return {
            "runsPerGame": float(statline.get("runsPerGame", 4.5)),
            "OPS": float(statline.get("ops", 0.73)),
            "wRC+": float(statline.get("battingAverage", 0.25)) * 400,
            "runs_last_5": runs_last_5
        }
    except Exception:
        return {
            "runsPerGame": 4.5,
            "OPS": 0.73,
            "wRC+": 100,
            "runs_last_5": 4.5
        }