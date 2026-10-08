#!/usr/bin/env python3
"""
Ocean Regatta - Participant Registry Management Utility
Manages participants.json: checking registration, parsing issue forms, adding/updating entries.
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone


def load_participants(file_path):
    if not os.path.exists(file_path):
        return {"schema_version": "1.0", "updated_at": datetime.now(timezone.utc).isoformat(), "participants": {}}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "participants" not in data:
                data["participants"] = {}
            return data
    except Exception as e:
        print(f"[manage_participants] Error reading {file_path}: {e}", file=sys.stderr)
        return {"schema_version": "1.0", "updated_at": datetime.now(timezone.utc).isoformat(), "participants": {}}


def save_participants(file_path, data):
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    # Sort participants by key for clean deterministic git diffs
    data["participants"] = dict(sorted(data.get("participants", {}).items(), key=lambda x: x[0]))
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"[manage_participants] Saved registry to {file_path}")


def check_participant(file_path, username):
    data = load_participants(file_path)
    user_key = (username or "").strip().lstrip("@").lower()
    participants = data.get("participants", {})

    if user_key in participants:
        entry = participants[user_key]
        status = entry.get("status", "approved")
        if status == "approved":
            res = {
                "registered": True,
                "username": entry.get("username", username),
                "display_name": entry.get("display_name") or entry.get("team") or entry.get("username", username),
                "team": entry.get("team", username),
                "affiliation": entry.get("affiliation", ""),
                "status": status,
                "edition": entry.get("edition", "")
            }
            print(json.dumps(res))
            return 0
        else:
            res = {
                "registered": False,
                "reason": f"Participant status is '{status}'",
                "username": username
            }
            print(json.dumps(res))
            return 1

    res = {
        "registered": False,
        "reason": "Not found in registry",
        "username": username
    }
    print(json.dumps(res))
    return 1


def parse_issue_form(body_text, fallback_user=None):
    """
    Parses GitHub Issue Form Markdown output.
    Looks for headers like:
    ### GitHub Username
    octocat

    ### Team / Competitor Name
    My Team
    """
    result = {
        "username": "",
        "team": "",
        "affiliation": "",
        "motivation": ""
    }

    if not body_text:
        if fallback_user:
            result["username"] = fallback_user.lstrip("@")
            result["team"] = fallback_user.lstrip("@")
        return result

    # Regex patterns for issue form headers
    patterns = {
        "username": r"###\s*GitHub\s*Username\s*\n+([^\n#]+)",
        "team": r"###\s*Team\s*(?:\/|\band\b)?\s*Competitor\s*Name\s*\n+([^\n#]+)",
        "affiliation": r"###\s*Affiliation\s*(?:\/|\band\b)?\s*Institution\s*\n+([^\n#]+)",
        "motivation": r"###\s*Brief\s*Strategy\s*(?:\/|\band\b)?\s*Motivation\s*\n+([^\n#]+)"
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, body_text, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            # GitHub issue form markdown might contain _No response_ if optional
            if val.lower() != "_no response_":
                result[key] = val

    # Clean username
    if result["username"]:
        result["username"] = result["username"].strip().lstrip("@")
    elif fallback_user:
        result["username"] = fallback_user.strip().lstrip("@")

    # Clean team / fallback to username
    if not result["team"]:
        result["team"] = result["username"] or "Independent"

    return result


def add_or_update_participant(file_path, username, team, display_name=None, affiliation=None, status="approved", approved_by="admin", issue_number=None, edition=None):
    user_key = (username or "").strip().lstrip("@").lower()
    clean_username = (username or "").strip().lstrip("@")
    if not user_key:
        print("[manage_participants] Error: Empty username provided", file=sys.stderr)
        return False

    data = load_participants(file_path)
    now_iso = datetime.now(timezone.utc).isoformat()

    existing = data.get("participants", {}).get(user_key, {})
    reg_date = existing.get("registered_at", now_iso)

    data["participants"][user_key] = {
        "username": clean_username,
        "team": team or clean_username,
        "display_name": display_name or team or clean_username,
        "affiliation": affiliation if affiliation is not None else existing.get("affiliation", ""),
        "status": status,
        "edition": edition or existing.get("edition") or "2026",
        "registered_at": reg_date,
        "approved_at": now_iso,
        "approved_by": approved_by,
        "issue_number": int(issue_number) if issue_number else existing.get("issue_number")
    }

    save_participants(file_path, data)
    print(f"[manage_participants] Successfully registered participant: {clean_username} ({display_name or team})")
    return True


def list_participants(file_path):
    data = load_participants(file_path)
    participants = data.get("participants", {})
    print(f"Total Registered Participants: {len(participants)}")
    print(f"{'Username':<20} {'Status':<10} {'Team / Display Name':<30} {'Affiliation':<25}")
    print("-" * 85)
    for k, v in participants.items():
        print(f"{v.get('username', k):<20} {v.get('status', 'unknown'):<10} {v.get('display_name', ''):<30} {v.get('affiliation', ''):<25}")


def main():
    parser = argparse.ArgumentParser(description="Manage Ocean Regatta participant registry")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # Check
    check_p = subparsers.add_parser("check", help="Check if user is registered and approved")
    check_p.add_argument("--file", default="participants.json", help="Path to participants.json")
    check_p.add_argument("--username", required=True, help="GitHub login to verify")

    # Add / Update
    add_p = subparsers.add_parser("add", help="Add or update a participant")
    add_p.add_argument("--file", default="participants.json", help="Path to participants.json")
    add_p.add_argument("--username", required=True, help="GitHub username")
    add_p.add_argument("--team", required=True, help="Team name")
    add_p.add_argument("--display-name", default=None, help="Display name (defaults to team)")
    add_p.add_argument("--affiliation", default="", help="Affiliation/University/Company")
    add_p.add_argument("--status", default="approved", choices=["approved", "suspended"], help="Participant status")
    add_p.add_argument("--edition", default=None, help="Target regatta edition (e.g. 2026)")
    add_p.add_argument("--approved-by", default="admin", help="Organizer login who approved")
    add_p.add_argument("--issue-number", type=int, default=None, help="GitHub issue number")

    # Parse Issue Form
    parse_p = subparsers.add_parser("parse-issue", help="Parse GitHub Issue Form markdown body")
    parse_p.add_argument("--body-file", help="Path to text file containing issue body")
    parse_p.add_argument("--body-text", help="Raw issue body string")
    parse_p.add_argument("--fallback-user", help="Fallback username (issue creator)")

    # List
    list_p = subparsers.add_parser("list", help="List participants")
    list_p.add_argument("--file", default="participants.json", help="Path to participants.json")

    args = parser.parse_args()

    if args.action == "check":
        sys.exit(check_participant(args.file, args.username))

    elif args.action == "add":
        ok = add_or_update_participant(
            file_path=args.file,
            username=args.username,
            team=args.team,
            display_name=args.display_name,
            affiliation=args.affiliation,
            status=args.status,
            edition=args.edition,
            approved_by=args.approved_by,
            issue_number=args.issue_number
        )
        sys.exit(0 if ok else 1)

    elif args.action == "parse-issue":
        text = ""
        if args.body_file and os.path.exists(args.body_file):
            with open(args.body_file, "r", encoding="utf-8") as f:
                text = f.read()
        elif args.body_text:
            text = args.body_text
        res = parse_issue_form(text, args.fallback_user)
        print(json.dumps(res, indent=2))
        sys.exit(0)

    elif args.action == "list":
        list_participants(args.file)
        sys.exit(0)


if __name__ == "__main__":
    main()

