#!/usr/bin/env python3
"""
Ocean Regatta - Automated Static Leaderboard and Badge Engine
Updates docs/data/leaderboard.json directly from simulation scoring_result.json.
Zero external backend servers required - 100% static GitHub Pages compatible.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone

BADGE_CATALOG = {
    "QUAY_SOVEREIGN": {
        "icon": "\U0001f451",
        "name": "Quay Sovereign",
        "category": "Exclusive",
        "desc": "Retained the #1 rank on the leaderboard continuously for > 72 hours",
        "exclusive": True
    },
    "SPEED_DEMON": {
        "icon": "\u26a1",
        "name": "Speed Demon",
        "category": "Exclusive",
        "desc": "Fastest elapsed time on a fully completed course without collision",
        "exclusive": True
    },
    "SEA_TURTLE": {
        "icon": "\U0001f422",
        "name": "Sea Turtle",
        "category": "Exclusive",
        "desc": "Most cautious and slowest navigation completing the full course",
        "exclusive": True
    },
    "SNIPER": {
        "icon": "\U0001f3af",
        "name": "Sniper",
        "category": "Exclusive",
        "desc": "High precision navigation clearing all waypoints with minimal deviation",
        "exclusive": True
    },
    "WATT_MISER": {
        "icon": "\U0001f50b",
        "name": "Watt Miser",
        "category": "Exclusive",
        "desc": "Lowest cumulative thruster energy expenditure on a validated run",
        "exclusive": True
    },
    "SONAR_WHISPERER": {
        "icon": "\U0001f987",
        "name": "Sonar Whisperer",
        "category": "Exclusive",
        "desc": "Maintained Ping2 lateral wall distance strictly within 5.0 ± 0.15 m across the Pier Corridor",
        "exclusive": True
    },
    "POSEIDONS_CHOSEN": {
        "icon": "\U0001f531",
        "name": "Poseidon's Chosen",
        "category": "Exclusive",
        "desc": "Completed course under severe procedural sea state (current ≥ 0.65 m/s, battery wear ≤ 0.90)",
        "exclusive": True
    },
    "MINIMALIST": {
        "icon": "\U0001f3f9",
        "name": "Minimalist",
        "category": "Exclusive",
        "desc": "Course cleared with the fewest total evaluation attempts",
        "exclusive": True
    },
    "KRAKENS_GRIP": {
        "icon": "\U0001f419",
        "name": "Kraken's Grip",
        "category": "Secret",
        "desc": "Survived extreme vortex currents (accumulated ≥ 720° yaw rotation while clearing waypoints)",
        "exclusive": False
    },
    "SIRENS_CALL": {
        "icon": "\U0001f9dc\u200d\u2640\ufe0f",
        "name": "Siren's Call",
        "category": "Standard",
        "desc": "Skimmed within < 1.5 m of the Cardinal mark during safe rounding without colliding",
        "exclusive": False
    },
    "NAVIGATOR": {
        "icon": "\U0001f9ed",
        "name": "Navigator",
        "category": "Standard",
        "desc": "Compliant IALA cardinal buoy rounding on regulatory side",
        "exclusive": False
    },
    "DRIFT_MASTER": {
        "icon": "\U0001f30a",
        "name": "Drift Master",
        "category": "Standard",
        "desc": "Maintained pier corridor standoff without critical drift",
        "exclusive": False
    },
    "EDGE_OF_GLORY": {
        "icon": "\U0001f4d0",
        "name": "Edge of Glory",
        "category": "Standard",
        "desc": "Skimmed within 1.01 m to 1.15 m of the pier wall without triggering critical contact",
        "exclusive": False
    },
    "LEAD_FOOT": {
        "icon": "\U0001f680",
        "name": "Lead Foot",
        "category": "Standard",
        "desc": "Maintained thrusters clamped at 100% saturation (±50 N) for > 85% of the run",
        "exclusive": False
    },
    "CRAB_WALK": {
        "icon": "\U0001f980",
        "name": "Crab Walk",
        "category": "Fun",
        "desc": "Cleared a channel gate or leg while navigating in reverse",
        "exclusive": False
    },
    "DONUT_KING": {
        "icon": "\U0001f369",
        "name": "Donut King",
        "category": "Fun",
        "desc": "Completed > 3 consecutive rotations in place (> 1080°) without linear forward progress",
        "exclusive": False
    },
    "PID_TREMORS": {
        "icon": "\U0001f39b\ufe0f",
        "name": "PID Tremors",
        "category": "Fun",
        "desc": "Thruster command sign reversed > 120 times in under 30 seconds (high-frequency chattering)",
        "exclusive": False
    },
    "TIS_BUT_A_SCRATCH": {
        "icon": "\U0001fa79",
        "name": "Tis But a Scratch",
        "category": "Resilience",
        "desc": "Scored > 15 pts on the immediate next submission following a fatal collision",
        "exclusive": False
    },
    "ESPRESSO_POWERED": {
        "icon": "\u2615",
        "name": "Espresso Powered",
        "category": "Grind",
        "desc": "Submitted ≥ 5 evaluation runs within a rolling 6-hour window",
        "exclusive": False
    },
    "DAWN_PATROL": {
        "icon": "\U0001f305",
        "name": "Dawn Patrol",
        "category": "Standard",
        "desc": "Submission evaluated at dawn between 05:00 and 07:30 UTC",
        "exclusive": False
    },
    "NIGHT_OWL": {
        "icon": "\U0001f989",
        "name": "Night Owl",
        "category": "Standard",
        "desc": "Submission evaluated between 23:00 and 04:00 UTC",
        "exclusive": False
    },
    "TITANIC": {
        "icon": "\U0001f6a2",
        "name": "Titanic",
        "category": "Standard",
        "desc": "First spectacular collision with the pier wall or obstacle",
        "exclusive": False
    },
    "DAVY_JONES_LOCKER": {
        "icon": "\u2693",
        "name": "Davy Jones' Locker",
        "category": "Consolation",
        "desc": "Run terminated, collided, or timed out before clearing Gate 1",
        "exclusive": False
    },
}


def update_leaderboard(result_file, leaderboard_file, team_name, display_name=None, timestamp_str=None):
    if not os.path.exists(result_file):
        print(f"Error: Result file {result_file} not found.", file=sys.stderr)
        return False

    with open(result_file, "r", encoding="utf-8") as f:
        res = json.load(f)

    if not os.path.exists(leaderboard_file):
        os.makedirs(os.path.dirname(os.path.abspath(leaderboard_file)), exist_ok=True)
        data = {
            "edition": "2026",
            "course_name": "Ocean Regatta 2026 (Channel and Sonar Pier)",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "teams": [],
            "all_badges": [dict(id=k, **v) for k, v in BADGE_CATALOG.items()]
        }
    else:
        with open(leaderboard_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    if not timestamp_str:
        now_dt = datetime.now(timezone.utc)
    else:
        now_dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

    teams = data.get("teams", [])
    team_entry = next((t for t in teams if t.get("team") == team_name), None)

    try:
        score = round(float(res.get("score", 0.0)), 3)
    except (ValueError, TypeError):
        score = 0.0

    try:
        sim_time = round(float(res.get("sim_time", res.get("total_time", 0.0))), 2)
    except (ValueError, TypeError):
        sim_time = 0.0

    success = bool(res.get("success", False))
    collision = bool(res.get("collision", False))
    drift_exceeded = bool(res.get("critical_drift_exceeded", False))

    # Minimum floor score: ensure at least 2.0 pts if no collision
    if not collision and score < 2.0:
        score = 2.0

    wp_cleared = int(res.get("waypoints_cleared", 0))
    wp_total = int(res.get("total_waypoints", len(res.get("waypoints", [])) or 11))

    status = "COMPLETED" if success else ("COLLISION" if collision else "TIMEOUT")

    if not team_entry:
        team_entry = {
            "team": team_name,
            "display_name": display_name or team_name,
            "score": score,
            "sim_time": sim_time,
            "status": status,
            "waypoints": f"{wp_cleared}/{wp_total}",
            "total_runs": 1,
            "success_runs": 1 if success else 0,
            "last_submission": now_dt.isoformat(),
            "badges": []
        }
        teams.append(team_entry)
    else:
        team_entry["total_runs"] = team_entry.get("total_runs", 0) + 1
        if success:
            team_entry["success_runs"] = team_entry.get("success_runs", 0) + 1
        team_entry["last_submission"] = now_dt.isoformat()
        if display_name:
            team_entry["display_name"] = display_name

        old_score = float(team_entry.get("score", 0.0))
        old_time = float(team_entry.get("sim_time", 99999.0))
        # Keep best run: higher score, or equal score with faster completion
        if (score > old_score) or (score == old_score and sim_time < old_time and sim_time > 0):
            team_entry["score"] = score
            team_entry["sim_time"] = sim_time
            team_entry["status"] = status
            team_entry["waypoints"] = f"{wp_cleared}/{wp_total}"

    # Award cumulative standard badges
    existing_badge_names = {b["name"] for b in team_entry.get("badges", [])}

    def add_standard_badge(b_key):
        b_info = BADGE_CATALOG.get(b_key)
        if b_info and b_info["name"] not in existing_badge_names:
            team_entry["badges"].append(b_info.copy())
            existing_badge_names.add(b_info["name"])

    if collision:
        add_standard_badge("TITANIC")
    if now_dt.hour >= 23 or now_dt.hour < 4:
        add_standard_badge("NIGHT_OWL")
    if 5 <= now_dt.hour < 8:
        add_standard_badge("DAWN_PATROL")
    if wp_cleared >= 4:
        add_standard_badge("NAVIGATOR")
    if success and not drift_exceeded:
        add_standard_badge("DRIFT_MASTER")
    if not success and wp_cleared == 0:
        add_standard_badge("DAVY_JONES_LOCKER")

    # Clear and re-calculate dynamic exclusive badges across all teams
    for t in teams:
        t["badges"] = [b for b in t.get("badges", []) if not b.get("exclusive", False)]

    successful_teams = [t for t in teams if t.get("status") == "COMPLETED" and float(t.get("sim_time", 0)) > 0]
    if successful_teams:
        speed_demon = min(successful_teams, key=lambda t: float(t["sim_time"]))
        speed_demon["badges"].append(BADGE_CATALOG["SPEED_DEMON"].copy())

        sea_turtle = max(successful_teams, key=lambda t: float(t["sim_time"]))
        sea_turtle["badges"].append(BADGE_CATALOG["SEA_TURTLE"].copy())

        sniper = max(successful_teams, key=lambda t: float(t["score"]))
        sniper["badges"].append(BADGE_CATALOG["SNIPER"].copy())

        minimalist = min(successful_teams, key=lambda t: t.get("total_runs", 999))
        minimalist["badges"].append(BADGE_CATALOG["MINIMALIST"].copy())

    # Sort descending by score, ascending by sim_time
    teams.sort(key=lambda t: (-float(t.get("score", 0)), float(t.get("sim_time", 99999)) if float(t.get("sim_time", 0)) > 0 else 99999.0))

    for idx, t in enumerate(teams, 1):
        t["rank"] = idx

    data["teams"] = teams
    data["last_updated"] = now_dt.isoformat()
    data["all_badges"] = [dict(id=k, **v) for k, v in BADGE_CATALOG.items()]

    with open(leaderboard_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[update_leaderboard] Leaderboard updated successfully for team: {team_name} (Score: {score}, Rank: {team_entry.get('rank')})")
    return True


def main():
    parser = argparse.ArgumentParser(description="Update static Ocean Regatta leaderboard.json")
    parser.add_argument("--result", required=True, help="Path to simulation scoring_result.json")
    parser.add_argument("--leaderboard", required=True, help="Path to docs/data/leaderboard.json")
    parser.add_argument("--team", required=True, help="GitHub login / Team handle")
    parser.add_argument("--display-name", default=None, help="Optional friendly display name")
    parser.add_argument("--timestamp", default=None, help="Optional ISO timestamp")

    args = parser.parse_args()
    success = update_leaderboard(
        result_file=args.result,
        leaderboard_file=args.leaderboard,
        team_name=args.team,
        display_name=args.display_name,
        timestamp_str=args.timestamp
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

