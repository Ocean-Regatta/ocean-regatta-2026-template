#!/usr/bin/env python3
"""
Unit tests for scripts/check_submission_window.py
"""

import os
import sys
import json
import tempfile
import unittest
import subprocess
from datetime import datetime, timezone, timedelta

# Add repository root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.check_submission_window import (
    parse_iso_datetime,
    format_human_duration,
    resolve_edition_window,
    check_submission_window,
    load_editions_file
)


class TestSubmissionWindow(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.editions_path = os.path.join(self.test_dir.name, "editions.json")
        self.participants_path = os.path.join(self.test_dir.name, "participants.json")

        self.sample_editions = {
            "schema_version": "1.0",
            "default_edition": "2026",
            "editions": {
                "2026": {
                    "name": "Ocean Regatta 2026",
                    "description": "2026 Competition",
                    "opening_datetime": "2026-10-01T00:00:00Z",
                    "closing_datetime": "2026-10-31T23:59:59Z",
                    "sessions": {
                        "round_1": {
                            "name": "Round 1 Session",
                            "opening_datetime": "2026-10-05T08:00:00Z",
                            "closing_datetime": "2026-10-10T18:00:00Z"
                        }
                    }
                },
                "2025": {
                    "name": "Ocean Regatta 2025",
                    "opening_datetime": "2025-10-01T00:00:00Z",
                    "closing_datetime": "2025-10-31T23:59:59Z"
                }
            }
        }
        with open(self.editions_path, "w", encoding="utf-8") as f:
            json.dump(self.sample_editions, f)

        self.sample_participants = {
            "participants": {
                "alice": {
                    "username": "Alice",
                    "team": "Team Alice",
                    "display_name": "Alice in Boatland",
                    "edition": "2026"
                },
                "bob_2025": {
                    "username": "Bob",
                    "team": "Team Bob",
                    "edition": "2025"
                }
            }
        }
        with open(self.participants_path, "w", encoding="utf-8") as f:
            json.dump(self.sample_participants, f)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_parse_iso_datetime(self):
        # 'Z' suffix
        dt1 = parse_iso_datetime("2026-10-08T14:30:00Z")
        self.assertEqual(dt1, datetime(2026, 10, 8, 14, 30, 0, tzinfo=timezone.utc))

        # Offset +02:00
        dt2 = parse_iso_datetime("2026-10-08T16:30:00+02:00")
        self.assertEqual(dt2, datetime(2026, 10, 8, 14, 30, 0, tzinfo=timezone.utc))

        # Naive string defaults to UTC
        dt3 = parse_iso_datetime("2026-10-08 14:30:00")
        self.assertEqual(dt3, datetime(2026, 10, 8, 14, 30, 0, tzinfo=timezone.utc))

        # Numeric epoch
        dt4 = parse_iso_datetime(1791469800)
        self.assertEqual(dt4.tzinfo, timezone.utc)

    def test_format_human_duration(self):
        self.assertEqual(format_human_duration(86400 * 3 + 3600 * 4 + 60 * 12), "3 days, 4 hours, 12 minutes")
        self.assertEqual(format_human_duration(3600 * 2 + 60 * 5), "2 hours, 5 minutes")
        self.assertEqual(format_human_duration(45), "45 seconds")
        self.assertEqual(format_human_duration(86400), "1 day")

    def test_resolve_default_edition(self):
        data = load_editions_file(self.editions_path)
        window = resolve_edition_window(data)
        self.assertEqual(window["edition_id"], "2026")
        self.assertEqual(window["edition_name"], "Ocean Regatta 2026")
        self.assertEqual(window["opening_dt"], datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(window["closing_dt"], datetime(2026, 10, 31, 23, 59, 59, tzinfo=timezone.utc))

    def test_resolve_specific_session(self):
        data = load_editions_file(self.editions_path)
        window = resolve_edition_window(data, edition_key="2026", session_key="round_1")
        self.assertEqual(window["session_id"], "round_1")
        self.assertEqual(window["session_name"], "Round 1 Session")
        self.assertEqual(window["opening_dt"], datetime(2026, 10, 5, 8, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(window["closing_dt"], datetime(2026, 10, 10, 18, 0, 0, tzinfo=timezone.utc))

    def test_resolve_participant_edition(self):
        data = load_editions_file(self.editions_path)
        window = resolve_edition_window(
            data,
            participants_file=self.participants_path,
            username="bob_2025"
        )
        self.assertEqual(window["edition_id"], "2025")

    def test_check_within_window(self):
        res = check_submission_window(
            editions_file=self.editions_path,
            submission_time_input="2026-10-15T12:00:00Z",
            edition_key="2026",
            username="Alice",
            display_name="Alice in Boatland"
        )
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["status"], "within_window")
        self.assertEqual(res["exit_code"], 0)
        self.assertIsNone(res["comment_markdown"])

    def test_check_too_early(self):
        res = check_submission_window(
            editions_file=self.editions_path,
            submission_time_input="2026-09-20T00:00:00Z",
            edition_key="2026",
            username="Alice",
            display_name="Alice in Boatland"
        )
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["status"], "too_early")
        self.assertEqual(res["exit_code"], 1)
        self.assertIn("Evaluation Aborted: Submission Window Not Open", res["comment_markdown"])
        self.assertIn("@Alice", res["comment_markdown"])
        self.assertIn("Alice in Boatland", res["comment_markdown"])
        self.assertIn("11 days", res["comment_markdown"])

    def test_check_too_late(self):
        res = check_submission_window(
            editions_file=self.editions_path,
            submission_time_input="2026-11-05T12:00:00Z",
            edition_key="2026",
            username="Alice",
            display_name="Alice in Boatland"
        )
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["status"], "too_late")
        self.assertEqual(res["exit_code"], 2)
        self.assertIn("Evaluation Aborted: Submission Window Closed", res["comment_markdown"])
        self.assertIn("@Alice", res["comment_markdown"])
        self.assertIn("4 days, 12 hours", res["comment_markdown"])

    def test_cli_execution(self):
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "check_submission_window.py")
        )

        # On-time CLI test
        cmd_ok = [
            sys.executable, script_path, "check",
            "--file", self.editions_path,
            "--edition", "2026",
            "--submission-time", "2026-10-10T12:00:00Z",
            "--username", "tester"
        ]
        ret_ok = subprocess.run(cmd_ok, capture_output=True, text=True)
        self.assertEqual(ret_ok.returncode, 0)
        self.assertIn("PASS", ret_ok.stdout)

        # Too early CLI test
        comment_file = os.path.join(self.test_dir.name, "comment_out.md")
        cmd_early = [
            sys.executable, script_path, "check",
            "--file", self.editions_path,
            "--edition", "2026",
            "--submission-time", "2026-09-01T00:00:00Z",
            "--username", "tester",
            "--comment-file", comment_file
        ]
        ret_early = subprocess.run(cmd_early, capture_output=True, text=True)
        self.assertEqual(ret_early.returncode, 1)
        self.assertTrue(os.path.exists(comment_file))
        with open(comment_file, "r") as f:
            content = f.read()
            self.assertIn("Submission Window Not Open", content)

        # Too late CLI test
        cmd_late = [
            sys.executable, script_path, "check",
            "--file", self.editions_path,
            "--edition", "2026",
            "--submission-time", "2026-11-10T00:00:00Z",
            "--username", "tester"
        ]
        ret_late = subprocess.run(cmd_late, capture_output=True, text=True)
        self.assertEqual(ret_late.returncode, 2)


if __name__ == "__main__":
    unittest.main()

