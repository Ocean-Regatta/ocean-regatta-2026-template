#!/usr/bin/env python3
"""
Unit tests for scripts/verify_submission.py
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.verify_submission import (
    CheckStatus,
    CheckResult,
    SubmissionContext,
    GitHubClient,
    check_submission_target,
    check_participant_registration,
    check_submission_window_rule,
    check_evaluation_cooldown,
    run_all_checks,
)


class TestVerifySubmission(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.participants_file = os.path.join(self.test_dir.name, "participants.json")
        self.editions_file = os.path.join(self.test_dir.name, "editions.json")

        self.sample_participants = {
            "participants": {
                "alice": {
                    "username": "Alice",
                    "team": "Team Alpha",
                    "display_name": "Alice in Boatland",
                    "status": "approved",
                    "edition": "2026",
                },
                "suspended_user": {
                    "username": "SuspendedUser",
                    "team": "Trouble",
                    "status": "suspended",
                    "edition": "2026",
                },
            }
        }
        with open(self.participants_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_participants, f)

        self.sample_editions = {
            "default_edition": "2026",
            "editions": {
                "2026": {
                    "name": "Ocean Regatta 2026",
                    "opening_datetime": "2026-10-01T00:00:00Z",
                    "closing_datetime": "2026-10-31T23:59:59Z",
                }
            },
        }
        with open(self.editions_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_editions, f)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_target_branch_check(self):
        ctx_valid = SubmissionContext(repo="test/repo", pr_number=1, student_login="alice", base_ref="evaluation")
        res_valid = check_submission_target(ctx_valid)
        self.assertTrue(res_valid.passed)
        self.assertEqual(res_valid.status, CheckStatus.PASS)

        ctx_invalid = SubmissionContext(repo="test/repo", pr_number=1, student_login="alice", base_ref="main")
        res_invalid = check_submission_target(ctx_invalid)
        self.assertFalse(res_invalid.passed)
        self.assertEqual(res_invalid.status, CheckStatus.FAIL)

    def test_participant_registration_approved(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=1,
            student_login="alice",
            participants_file=self.participants_file,
        )
        res = check_participant_registration(ctx)
        self.assertTrue(res.passed)
        self.assertEqual(ctx.display_name, "Alice in Boatland")
        self.assertEqual(ctx.team_name, "Team Alpha")
        self.assertEqual(ctx.user_edition, "2026")
        self.assertIn("unregistered", res.labels_to_remove)

    def test_participant_registration_unregistered(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=1,
            student_login="bob_stranger",
            participants_file=self.participants_file,
        )
        res = check_participant_registration(ctx)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, CheckStatus.FAIL)
        self.assertIn("unregistered", res.labels_to_add)
        self.assertIn("Competitor Registration Request", res.comment_markdown)

    def test_participant_registration_suspended(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=1,
            student_login="suspended_user",
            participants_file=self.participants_file,
        )
        res = check_participant_registration(ctx)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, CheckStatus.FAIL)

    def test_submission_window_valid(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=1,
            student_login="alice",
            submission_time_input="2026-10-15T12:00:00Z",
            participants_file=self.participants_file,
            editions_file=self.editions_file,
        )
        res = check_submission_window_rule(ctx)
        self.assertTrue(res.passed)
        self.assertIn("submission-closed", res.labels_to_remove)

    def test_submission_window_too_early(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=1,
            student_login="alice",
            submission_time_input="2026-09-15T12:00:00Z",
            participants_file=self.participants_file,
            editions_file=self.editions_file,
        )
        res = check_submission_window_rule(ctx)
        self.assertFalse(res.passed)
        self.assertIn("submission-too-early", res.labels_to_add)

    def test_submission_window_too_late(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=1,
            student_login="alice",
            submission_time_input="2026-11-05T12:00:00Z",
            participants_file=self.participants_file,
            editions_file=self.editions_file,
        )
        res = check_submission_window_rule(ctx)
        self.assertFalse(res.passed)
        self.assertIn("submission-closed", res.labels_to_add)

    def test_force_eval_bypasses_window_and_cooldown(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=1,
            student_login="alice",
            pr_title="[force-eval] quick test",
            submission_time_input="2026-09-01T00:00:00Z",
            participants_file=self.participants_file,
            editions_file=self.editions_file,
        )
        self.assertTrue(ctx.force_eval)
        res_window = check_submission_window_rule(ctx)
        self.assertEqual(res_window.status, CheckStatus.SKIPPED)

        gh_client = MagicMock()
        res_cooldown = check_evaluation_cooldown(ctx, gh_client)
        self.assertEqual(res_cooldown.status, CheckStatus.SKIPPED)

    def test_cooldown_active(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=42,
            student_login="alice",
            cooldown_seconds=3600,
        )
        gh_client = MagicMock()
        gh_client.is_active.return_value = True
        # Last run was 10 minutes ago
        gh_client.get_last_completed_run_time.return_value = datetime.now(timezone.utc) - timedelta(minutes=10)

        res = check_evaluation_cooldown(ctx, gh_client)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, CheckStatus.FAIL)
        self.assertIn("cooldown active", res.comment_markdown)
        self.assertIn("50 more minute", res.comment_markdown)

    def test_cooldown_satisfied(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=42,
            student_login="alice",
            cooldown_seconds=3600,
        )
        gh_client = MagicMock()
        gh_client.is_active.return_value = True
        # Last run was 2 hours ago
        gh_client.get_last_completed_run_time.return_value = datetime.now(timezone.utc) - timedelta(hours=2)

        res = check_evaluation_cooldown(ctx, gh_client)
        self.assertTrue(res.passed)
        self.assertEqual(res.status, CheckStatus.PASS)

    def test_pipeline_overall_success(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=10,
            student_login="alice",
            submission_time_input="2026-10-15T12:00:00Z",
            participants_file=self.participants_file,
            editions_file=self.editions_file,
            dry_run=True,
        )
        gh_client = MagicMock()
        gh_client.is_active.return_value = False

        passed, results = run_all_checks(ctx, gh_client)
        self.assertTrue(passed)
        self.assertEqual(len(results), 4)

    def test_pipeline_failure_aborts_early(self):
        ctx = SubmissionContext(
            repo="test/repo",
            pr_number=10,
            student_login="unknown_person",
            participants_file=self.participants_file,
            editions_file=self.editions_file,
            dry_run=True,
        )
        gh_client = MagicMock()
        gh_client.is_active.return_value = False

        passed, results = run_all_checks(ctx, gh_client)
        self.assertFalse(passed)
        # Should stop after registration check (target branch passed, registration failed)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[1].name, "participant_registration")

    def test_github_client_api_request(self):
        gh = GitHubClient(repo="Ocean-Regatta/test-repo", token="fake_token", dry_run=False)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"workflow_runs": [{"pull_requests": [{"number": 12}], "created_at": "2026-10-09T12:00:00Z"}]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            dt = gh.get_last_completed_run_time("evaluate.yml", 12)
            self.assertIsNotNone(dt)
            self.assertEqual(dt.year, 2026)


if __name__ == "__main__":
    unittest.main()
