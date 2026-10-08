#!/usr/bin/env python3
"""
Ocean Regatta - Submission Window & Edition Gatekeeper Utility
Verifies whether a pull request submission is submitted within the allowed opening and closing dates.
Produces personalised Markdown messages for early, valid, or late submissions.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple


def parse_iso_datetime(dt_input: Any, default_tz=timezone.utc) -> datetime:
    """
    Parses an ISO 8601 string or numeric timestamp into an aware UTC datetime object.
    Supports 'Z' suffix, numeric epochs, and offset strings (e.g., '+02:00').
    """
    if isinstance(dt_input, (int, float)):
        return datetime.fromtimestamp(dt_input, tz=timezone.utc)

    if not isinstance(dt_input, str):
        raise ValueError(f"Invalid datetime input type: {type(dt_input)}")

    dt_str = dt_input.strip()
    if not dt_str:
        raise ValueError("Datetime string is empty")

    # Handle unix epoch string
    if dt_str.isdigit():
        return datetime.fromtimestamp(int(dt_str), tz=timezone.utc)

    # Standardize 'Z' to '+00:00' for universal ISO parsing
    if dt_str.endswith("Z") or dt_str.endswith("z"):
        dt_str = dt_str[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(dt_str)
    except Exception as e:
        raise ValueError(f"Could not parse ISO datetime string '{dt_input}': {e}")

    # Attach default timezone if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz)

    # Normalize to UTC
    return dt.astimezone(timezone.utc)


def format_human_duration(total_seconds: float) -> str:
    """
    Converts seconds into a clean, human-friendly string (e.g. '3 days, 4 hours, 12 minutes').
    """
    seconds = int(abs(total_seconds))
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if not parts or (days == 0 and hours == 0 and minutes < 3):
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    return ", ".join(parts)


def format_utc_display(dt: datetime) -> str:
    """Formats an aware UTC datetime into a standardized string."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_editions_file(file_path: str) -> Dict[str, Any]:
    """Loads and validates the editions.json file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Editions configuration file not found at: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in editions file {file_path}: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Editions file must contain a JSON object, got {type(data)}")

    if "editions" not in data or not isinstance(data["editions"], dict):
        raise ValueError("Editions file must contain an 'editions' dictionary")

    return data


def extract_dates_from_dict(d: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Extracts opening and closing datetime strings from an edition or session dict."""
    opening_keys = [
        "opening_datetime", "opening_time", "opening",
        "start_datetime", "start_time", "start_date", "start"
    ]
    closing_keys = [
        "closing_datetime", "closing_time", "closing",
        "end_datetime", "end_time", "end_date", "end"
    ]

    opening_val = None
    for k in opening_keys:
        if k in d and d[k]:
            opening_val = str(d[k])
            break

    closing_val = None
    for k in closing_keys:
        if k in d and d[k]:
            closing_val = str(d[k])
            break

    return opening_val, closing_val


def resolve_edition_window(
    editions_data: Dict[str, Any],
    edition_key: Optional[str] = None,
    session_key: Optional[str] = None,
    participants_file: Optional[str] = None,
    username: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves the exact opening and closing datetimes for the target edition and session.
    """
    editions_map = editions_data.get("editions", {})
    if not editions_map:
        raise ValueError("No editions defined in configuration")

    # 1. If username and participants file provided, check if user is bound to an edition
    if not edition_key and participants_file and username and os.path.exists(participants_file):
        try:
            with open(participants_file, "r", encoding="utf-8") as pf:
                pdata = json.load(pf)
                user_clean = username.strip().lstrip("@").lower()
                user_entry = pdata.get("participants", {}).get(user_clean)
                if user_entry and user_entry.get("edition"):
                    edition_key = str(user_entry["edition"])
        except Exception:
            pass

    # 2. If no edition specified, resolve default
    if not edition_key:
        edition_key = (
            editions_data.get("default_edition") or
            editions_data.get("active_edition") or
            next(iter(editions_map.keys()))
        )

    edition_key_str = str(edition_key)
    if edition_key_str not in editions_map:
        avail = ", ".join(repr(k) for k in editions_map.keys())
        raise ValueError(f"Edition '{edition_key_str}' not found in configuration. Available: [{avail}]")

    edition_entry = editions_map[edition_key_str]
    edition_name = edition_entry.get("name", f"Ocean Regatta {edition_key_str}")

    session_name = None
    resolved_session_key = None
    opening_str = None
    closing_str = None

    sessions_map = edition_entry.get("sessions", {})

    # Check if a specific session is requested
    if session_key:
        session_key_str = str(session_key)
        if session_key_str not in sessions_map:
            avail_sessions = ", ".join(repr(k) for k in sessions_map.keys())
            raise ValueError(
                f"Session '{session_key_str}' not found in edition '{edition_key_str}'. "
                f"Available sessions: [{avail_sessions}]"
            )
        session_entry = sessions_map[session_key_str]
        session_name = session_entry.get("name", session_key_str)
        resolved_session_key = session_key_str
        opening_str, closing_str = extract_dates_from_dict(session_entry)

    # If no session specified, check edition-level dates first
    if not opening_str or not closing_str:
        ed_open, ed_close = extract_dates_from_dict(edition_entry)
        if ed_open and ed_close:
            opening_str, closing_str = ed_open, ed_close

    # If still not found, check sessions inside edition
    if (not opening_str or not closing_str) and sessions_map:
        # Check active session if declared
        active_sess_id = edition_entry.get("active_session")
        if active_sess_id and active_sess_id in sessions_map:
            session_entry = sessions_map[active_sess_id]
            resolved_session_key = active_sess_id
            session_name = session_entry.get("name", active_sess_id)
            opening_str, closing_str = extract_dates_from_dict(session_entry)
        elif len(sessions_map) == 1:
            sess_id, session_entry = next(iter(sessions_map.items()))
            resolved_session_key = sess_id
            session_name = session_entry.get("name", sess_id)
            opening_str, closing_str = extract_dates_from_dict(session_entry)

    if not opening_str or not closing_str:
        raise ValueError(
            f"Edition '{edition_key_str}' does not have valid opening and closing datetimes specified."
        )

    opening_dt = parse_iso_datetime(opening_str)
    closing_dt = parse_iso_datetime(closing_str)

    if opening_dt > closing_dt:
        raise ValueError(
            f"Invalid session window for edition '{edition_key_str}': "
            f"opening ({opening_str}) is later than closing ({closing_str})"
        )

    return {
        "edition_id": edition_key_str,
        "edition_name": edition_name,
        "session_id": resolved_session_key,
        "session_name": session_name,
        "description": edition_entry.get("description", ""),
        "opening_dt": opening_dt,
        "closing_dt": closing_dt,
        "opening_iso": opening_dt.isoformat(),
        "closing_iso": closing_dt.isoformat(),
        "opening_display": format_utc_display(opening_dt),
        "closing_display": format_utc_display(closing_dt),
    }


def generate_early_comment(
    window: Dict[str, Any],
    submission_dt: datetime,
    username: str,
    display_name: Optional[str] = None,
    team_name: Optional[str] = None
) -> str:
    """Generates a personalised Markdown rejection message for an early submission."""
    user_handle = username.strip().lstrip("@")
    effective_name = display_name or team_name or user_handle
    sub_str = format_utc_display(submission_dt)
    open_str = window["opening_display"]
    close_str = window["closing_display"]

    diff_seconds = (window["opening_dt"] - submission_dt).total_seconds()
    time_until_open = format_human_duration(diff_seconds)

    name_greeting = f"Hello @{user_handle}!"
    if effective_name and effective_name.lower() != user_handle.lower():
        name_greeting = f"Hello **{effective_name}** (@{user_handle})!"

    session_detail = ""
    if window.get("session_name"):
        session_detail = f"| **Session** | **{window['session_name']}** |\n"

    md = (
        f"> ⏳ **Evaluation Aborted: Submission Window Not Open**\n\n"
        f"{name_greeting}\n\n"
        f"Your pull request was not evaluated because submissions for **{window['edition_name']}** "
        f"are not currently open.\n\n"
        f"| Detail | Value |\n"
        f"| :--- | :--- |\n"
        f"| **Competitor / Team** | **{effective_name}** (@{user_handle}) |\n"
        f"| **Target Edition** | **{window['edition_name']}** (`{window['edition_id']}`) |\n"
        f"{session_detail}"
        f"| **Submission Received** | `{sub_str}` |\n"
        f"| **Window Opens** | `{open_str}` |\n"
        f"| **Window Closes** | `{close_str}` |\n"
        f"| **Time Until Opening** | **{time_until_open}** |\n\n"
        f"### ℹ️ Next Steps:\n"
        f"* Automated grading on the evaluation server runs exclusively during the active competition window.\n"
        f"* The submission portal officially opens on **`{open_str}`**.\n"
        f"* Please wait until the window is open before pushing new commits or reopening this pull request.\n\n"
        f"*(Tip for instructors/testing: add `[force-eval]` in the PR title to bypass)*\n"
    )
    return md


def generate_late_comment(
    window: Dict[str, Any],
    submission_dt: datetime,
    username: str,
    display_name: Optional[str] = None,
    team_name: Optional[str] = None
) -> str:
    """Generates a personalised Markdown rejection message for a late submission."""
    user_handle = username.strip().lstrip("@")
    effective_name = display_name or team_name or user_handle
    sub_str = format_utc_display(submission_dt)
    open_str = window["opening_display"]
    close_str = window["closing_display"]

    diff_seconds = (submission_dt - window["closing_dt"]).total_seconds()
    time_elapsed = format_human_duration(diff_seconds)

    name_greeting = f"Hello @{user_handle}!"
    if effective_name and effective_name.lower() != user_handle.lower():
        name_greeting = f"Hello **{effective_name}** (@{user_handle})!"

    session_detail = ""
    if window.get("session_name"):
        session_detail = f"| **Session** | **{window['session_name']}** |\n"

    md = (
        f"> ⛔ **Evaluation Aborted: Submission Window Closed**\n\n"
        f"{name_greeting}\n\n"
        f"Your pull request was not evaluated because the official submission deadline for **{window['edition_name']}** "
        f"has passed.\n\n"
        f"| Detail | Value |\n"
        f"| :--- | :--- |\n"
        f"| **Competitor / Team** | **{effective_name}** (@{user_handle}) |\n"
        f"| **Target Edition** | **{window['edition_name']}** (`{window['edition_id']}`) |\n"
        f"{session_detail}"
        f"| **Submission Received** | `{sub_str}` |\n"
        f"| **Window Opened** | `{open_str}` |\n"
        f"| **Window Closed (Deadline)** | `{close_str}` |\n"
        f"| **Time Elapsed Since Deadline** | **{time_elapsed}** |\n\n"
        f"### ℹ️ Notice:\n"
        f"* The competition session concluded on **`{close_str}`**.\n"
        f"* Automated simulations and leaderboard rankings are no longer accepted for this edition.\n"
        f"* If you believe this is an error or have an authorized extension from course staff, please reach out to the regatta organizers.\n\n"
        f"*(Tip for instructors/testing: add `[force-eval]` in the PR title to bypass)*\n"
    )
    return md


def check_submission_window(
    editions_file: str,
    submission_time_input: Optional[Any] = None,
    edition_key: Optional[str] = None,
    session_key: Optional[str] = None,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
    team_name: Optional[str] = None,
    participants_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates whether a submission is within the opening and closing time window.
    Returns structured results including status ('within_window', 'too_early', 'too_late'),
    delta descriptions, and personalised markdown comments.
    """
    editions_data = load_editions_file(editions_file)

    # Determine submission time
    if submission_time_input is not None and str(submission_time_input).strip():
        sub_dt = parse_iso_datetime(submission_time_input)
    else:
        sub_dt = datetime.now(timezone.utc)

    window = resolve_edition_window(
        editions_data=editions_data,
        edition_key=edition_key,
        session_key=session_key,
        participants_file=participants_file,
        username=username
    )

    clean_user = (username or "competitor").strip().lstrip("@")
    effective_name = display_name or team_name or clean_user

    open_dt = window["opening_dt"]
    close_dt = window["closing_dt"]

    if sub_dt < open_dt:
        diff_sec = (open_dt - sub_dt).total_seconds()
        human_diff = format_human_duration(diff_sec)
        comment_md = generate_early_comment(
            window=window,
            submission_dt=sub_dt,
            username=clean_user,
            display_name=effective_name,
            team_name=team_name
        )
        return {
            "status": "too_early",
            "is_valid": False,
            "exit_code": 1,
            "edition_id": window["edition_id"],
            "edition_name": window["edition_name"],
            "session_id": window["session_id"],
            "session_name": window["session_name"],
            "submission_time": sub_dt.isoformat(),
            "submission_display": format_utc_display(sub_dt),
            "opening_time": open_dt.isoformat(),
            "opening_display": window["opening_display"],
            "closing_time": close_dt.isoformat(),
            "closing_display": window["closing_display"],
            "diff_seconds": diff_sec,
            "diff_human": human_diff,
            "message": (
                f"Submission rejected: Submissions for '{window['edition_name']}' have not opened yet. "
                f"Window opens on {window['opening_display']} (in {human_diff})."
            ),
            "comment_markdown": comment_md
        }

    elif sub_dt > close_dt:
        diff_sec = (sub_dt - close_dt).total_seconds()
        human_diff = format_human_duration(diff_sec)
        comment_md = generate_late_comment(
            window=window,
            submission_dt=sub_dt,
            username=clean_user,
            display_name=effective_name,
            team_name=team_name
        )
        return {
            "status": "too_late",
            "is_valid": False,
            "exit_code": 2,
            "edition_id": window["edition_id"],
            "edition_name": window["edition_name"],
            "session_id": window["session_id"],
            "session_name": window["session_name"],
            "submission_time": sub_dt.isoformat(),
            "submission_display": format_utc_display(sub_dt),
            "opening_time": open_dt.isoformat(),
            "opening_display": window["opening_display"],
            "closing_time": close_dt.isoformat(),
            "closing_display": window["closing_display"],
            "diff_seconds": diff_sec,
            "diff_human": human_diff,
            "message": (
                f"Submission rejected: Deadline for '{window['edition_name']}' has passed. "
                f"Window closed on {window['closing_display']} ({human_diff} ago)."
            ),
            "comment_markdown": comment_md
        }

    else:
        remaining_sec = (close_dt - sub_dt).total_seconds()
        human_rem = format_human_duration(remaining_sec)
        return {
            "status": "within_window",
            "is_valid": True,
            "exit_code": 0,
            "edition_id": window["edition_id"],
            "edition_name": window["edition_name"],
            "session_id": window["session_id"],
            "session_name": window["session_name"],
            "submission_time": sub_dt.isoformat(),
            "submission_display": format_utc_display(sub_dt),
            "opening_time": open_dt.isoformat(),
            "opening_display": window["opening_display"],
            "closing_time": close_dt.isoformat(),
            "closing_display": window["closing_display"],
            "remaining_seconds": remaining_sec,
            "remaining_human": human_rem,
            "message": (
                f"Submission accepted: Submission at {format_utc_display(sub_dt)} is within window "
                f"[{window['opening_display']} -> {window['closing_display']}] for '{window['edition_name']}'. "
                f"Window closes in {human_rem}."
            ),
            "comment_markdown": None
        }


def list_editions_summary(editions_file: str) -> None:
    """Prints a terminal table of all editions and their current status."""
    data = load_editions_file(editions_file)
    now = datetime.now(timezone.utc)
    editions = data.get("editions", {})
    default_ed = data.get("default_edition") or data.get("active_edition")

    print("\n" + "=" * 115)
    print(" Ocean Regatta - Registered Editions & Submission Windows")
    print(f" Reference Clock: {format_utc_display(now)}")
    print("=" * 115)
    print(f"{'Edition ID':<16} {'Edition Name':<28} {'Status':<12} {'Opens (UTC)':<22} {'Closes (UTC)':<22} {'Info'}")
    print("-" * 115)

    for ed_id, ed_info in editions.items():
        is_default = (str(ed_id) == str(default_ed))
        tag = f"{ed_id} *" if is_default else str(ed_id)
        name = str(ed_info.get("name", ed_id))[:26]

        try:
            window = resolve_edition_window(data, edition_key=ed_id)
            open_dt = window["opening_dt"]
            close_dt = window["closing_dt"]

            if now < open_dt:
                status = "UPCOMING"
                info = f"Opens in {format_human_duration((open_dt - now).total_seconds())}"
            elif now > close_dt:
                status = "CLOSED"
                info = f"Closed {format_human_duration((now - close_dt).total_seconds())} ago"
            else:
                status = "ACTIVE"
                info = f"Closes in {format_human_duration((close_dt - now).total_seconds())}"

            print(
                f"{tag:<16} {name:<28} {status:<12} "
                f"{format_utc_display(open_dt)[:19]:<22} "
                f"{format_utc_display(close_dt)[:19]:<22} {info}"
            )
        except Exception as e:
            print(f"{tag:<16} {name:<28} {'ERROR':<12} {'-':<22} {'-':<22} {e}")

    print("=" * 115)
    print(" (* default edition)\n")


def main():
    parser = argparse.ArgumentParser(description="Ocean Regatta Submission Window & Edition Gatekeeper")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Command: check
    check_p = subparsers.add_parser("check", help="Verify submission timestamp against edition time window")
    check_p.add_argument("--file", "-f", default="editions.json", help="Path to editions.json")
    check_p.add_argument("--edition", "-e", default=None, help="Target edition ID (e.g. 2026)")
    check_p.add_argument("--session", "-s", default=None, help="Target session ID")
    check_p.add_argument("--submission-time", "-t", default=None, help="Submission ISO datetime or unix timestamp")
    check_p.add_argument("--username", "-u", default=None, help="GitHub login of participant")
    check_p.add_argument("--display-name", "-d", default=None, help="Display or team name")
    check_p.add_argument("--team", default=None, help="Team name")
    check_p.add_argument("--participants-file", default=None, help="Path to participants.json")
    check_p.add_argument("--comment-file", default=None, help="Write generated PR comment Markdown to this file")
    check_p.add_argument("--json-file", default=None, help="Write result JSON to this file")
    check_p.add_argument("--quiet", "-q", action="store_true", help="Suppress stdout messages")

    # Command: list
    list_p = subparsers.add_parser("list", help="List all editions and their current window statuses")
    list_p.add_argument("--file", "-f", default="editions.json", help="Path to editions.json")

    args = parser.parse_args()

    if args.action == "list":
        try:
            list_editions_summary(args.file)
            sys.exit(0)
        except Exception as e:
            print(f"Error listing editions: {e}", file=sys.stderr)
            sys.exit(3)

    elif args.action == "check":
        try:
            result = check_submission_window(
                editions_file=args.file,
                submission_time_input=args.submission_time,
                edition_key=args.edition,
                session_key=args.session,
                username=args.username,
                display_name=args.display_name,
                team_name=args.team,
                participants_file=args.participants_file
            )

            # Write comment file if requested
            if args.comment_file:
                with open(args.comment_file, "w", encoding="utf-8") as cf:
                    cf.write(result.get("comment_markdown") or "")

            # Write json file if requested
            if args.json_file:
                with open(args.json_file, "w", encoding="utf-8") as jf:
                    json.dump(result, jf, indent=2)

            # Console output
            if not args.quiet:
                if result["status"] == "within_window":
                    print(f"[check_submission_window] ✅ PASS: {result['message']}")
                elif result["status"] == "too_early":
                    print(f"::error::{result['message']}")
                    print(f"[check_submission_window] ⏳ TOO EARLY: {result['message']}", file=sys.stderr)
                elif result["status"] == "too_late":
                    print(f"::error::{result['message']}")
                    print(f"[check_submission_window] ⛔ TOO LATE: {result['message']}", file=sys.stderr)

            sys.exit(result["exit_code"])

        except Exception as e:
            print(f"::error::Configuration or gatekeeper error: {e}", file=sys.stderr)
            if args.json_file:
                with open(args.json_file, "w", encoding="utf-8") as jf:
                    json.dump({"status": "error", "message": str(e), "is_valid": False}, jf, indent=2)
            sys.exit(3)


if __name__ == "__main__":
    main()

