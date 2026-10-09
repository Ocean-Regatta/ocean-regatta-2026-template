#!/usr/bin/env python3
"""
Ocean Regatta - Unified Submission Verification Gatekeeper
Validates pull request submissions before simulation evaluation runs.

Consolidates all submission pre-checks into one unified pipeline:
  1. Target branch verification (must target 'evaluation')
  2. Competitor registration & approval verification (participants.json)
  3. Submission window verification (editions.json)
  4. Evaluation cooldown verification (GitHub Actions API)

Extensibility:
  To add a new pre-check:
  1. Define a function with signature: `def check_my_rule(ctx: SubmissionContext) -> CheckResult:`
  2. Append it to `ACTIVE_CHECKS` list.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

# Support relative or absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from scripts.check_submission_window import check_submission_window, parse_iso_datetime
except ImportError:
    from check_submission_window import check_submission_window, parse_iso_datetime


class CheckStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class CheckResult:
    """Represents the outcome of an individual pre-evaluation check."""

    def __init__(
        self,
        name: str,
        status: CheckStatus,
        message: str,
        comment_markdown: Optional[str] = None,
        labels_to_add: Optional[List[str]] = None,
        labels_to_remove: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.name = name
        self.status = status
        self.message = message
        self.comment_markdown = comment_markdown
        self.labels_to_add = labels_to_add or []
        self.labels_to_remove = labels_to_remove or []
        self.env_vars = env_vars or {}
        self.metadata = metadata or {}

    @property
    def passed(self) -> bool:
        return self.status in (CheckStatus.PASS, CheckStatus.SKIPPED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "passed": self.passed,
            "message": self.message,
            "labels_to_add": self.labels_to_add,
            "labels_to_remove": self.labels_to_remove,
            "env_vars": self.env_vars,
            "metadata": self.metadata,
        }


class SubmissionContext:
    """Holds all metadata, environment configuration, and inputs for a PR evaluation."""

    def __init__(
        self,
        repo: str,
        pr_number: int,
        student_login: str,
        base_ref: str = "evaluation",
        head_ref: str = "",
        pr_title: str = "",
        pr_body: str = "",
        submission_time_input: Optional[str] = None,
        cooldown_seconds: int = 3600,
        regatta_edition: str = "2026",
        participants_file: str = "participants.json",
        editions_file: str = "editions.json",
        gh_token: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.repo = repo
        self.pr_number = pr_number
        self.student_login = student_login.strip().lstrip("@")
        self.base_ref = base_ref.strip()
        self.head_ref = head_ref.strip()
        self.pr_title = pr_title or ""
        self.pr_body = pr_body or ""
        self.submission_time_input = submission_time_input
        self.cooldown_seconds = cooldown_seconds
        self.regatta_edition = regatta_edition
        self.participants_file = participants_file
        self.editions_file = editions_file
        self.gh_token = gh_token
        self.dry_run = dry_run

        # Participant metadata resolved during registration check
        self.display_name: str = self.student_login
        self.team_name: str = self.student_login
        self.user_edition: str = ""

    @property
    def force_eval(self) -> bool:
        """Checks if [force-eval] flag is present in PR title or description."""
        content = f"{self.pr_title} {self.pr_body}".lower()
        return "[force-eval]" in content

    @property
    def submission_time(self) -> datetime:
        """Resolves submission datetime in aware UTC."""
        if self.submission_time_input:
            try:
                return parse_iso_datetime(self.submission_time_input)
            except Exception:
                pass
        return datetime.now(timezone.utc)


class GitHubClient:
    """Lightweight GitHub REST API client using Python standard library."""

    def __init__(self, repo: str, token: Optional[str] = None, dry_run: bool = False):
        self.repo = repo
        self.token = token
        self.dry_run = dry_run

    def is_active(self) -> bool:
        return bool(self.token and self.repo and not self.dry_run)

    def _api_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Any]:
        if not self.is_active():
            print(f"[GitHubClient] (dry-run/offline) {method} {endpoint} - Payload: {data}")
            return 200, {}

        url = f"https://api.github.com/repos/{self.repo}{endpoint}"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Ocean-Regatta-Gatekeeper",
            },
            method=method,
        )
        if data is not None:
            body_bytes = json.dumps(data).encode("utf-8")
            req.data = body_bytes
            req.headers["Content-Type"] = "application/json"

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                resp_data = resp.read().decode("utf-8")
                return resp.status, json.loads(resp_data) if resp_data else {}
        except urllib.error.HTTPError as e:
            resp_data = e.read().decode("utf-8")
            try:
                err_json = json.loads(resp_data)
            except Exception:
                err_json = {"raw_error": resp_data}
            return e.code, err_json
        except Exception as e:
            return 0, {"error": str(e)}

    def post_pr_comment(self, pr_number: int, comment: str) -> bool:
        if not comment or not comment.strip():
            return True
        status, resp = self._api_request(
            f"/issues/{pr_number}/comments",
            method="POST",
            data={"body": comment},
        )
        if status in (200, 201):
            print(f"[verify_submission] Posted comment to PR #{pr_number}")
            return True
        else:
            print(f"[verify_submission] Warning: Failed to post PR comment (HTTP {status}): {resp}", file=sys.stderr)
            return False

    def add_labels(self, pr_number: int, labels: List[str]) -> bool:
        if not labels:
            return True
        status, resp = self._api_request(
            f"/issues/{pr_number}/labels",
            method="POST",
            data={"labels": labels},
        )
        if status in (200, 201):
            print(f"[verify_submission] Added labels to PR #{pr_number}: {labels}")
            return True
        else:
            print(f"[verify_submission] Warning: Failed to add labels {labels} (HTTP {status}): {resp}", file=sys.stderr)
            return False

    def remove_label(self, pr_number: int, label: str) -> bool:
        if not label:
            return True
        status, _ = self._api_request(
            f"/issues/{pr_number}/labels/{urllib.parse.quote(label)}",
            method="DELETE",
        )
        # 200 = removed, 404 = label wasn't attached
        return status in (200, 204, 404)

    def get_last_completed_run_time(self, workflow_name: str, pr_number: int) -> Optional[datetime]:
        """Fetches the completion or start timestamp of the last completed run for a PR."""
        if not self.is_active():
            return None

        status, data = self._api_request(
            f"/actions/workflows/{workflow_name}/runs?status=completed&per_page=20",
            method="GET",
        )
        if status != 200 or not isinstance(data, dict):
            print(f"[verify_submission] Warning: Could not fetch workflow runs (HTTP {status})", file=sys.stderr)
            return None

        workflow_runs = data.get("workflow_runs", [])
        for run in workflow_runs:
            prs = run.get("pull_requests", [])
            if any(p.get("number") == pr_number for p in prs):
                dt_str = run.get("created_at") or run.get("run_started_at")
                if dt_str:
                    try:
                        return parse_iso_datetime(dt_str)
                    except Exception:
                        pass
        return None


# ==============================================================================
# INDIVIDUAL PRE-CHECK DEFINITIONS
# ==============================================================================


def check_submission_target(ctx: SubmissionContext) -> CheckResult:
    """Verifies that the PR targets the 'evaluation' branch."""
    if ctx.base_ref != "evaluation":
        return CheckResult(
            name="target_branch",
            status=CheckStatus.FAIL,
            message=f"Direct PRs must target the 'evaluation' branch. Received target: '{ctx.base_ref}'",
        )
    return CheckResult(
        name="target_branch",
        status=CheckStatus.PASS,
        message=f"Target branch valid: '{ctx.base_ref}'",
    )


def check_participant_registration(ctx: SubmissionContext) -> CheckResult:
    """Verifies that the competitor is registered and approved in participants.json."""
    if not os.path.exists(ctx.participants_file):
        return CheckResult(
            name="participant_registration",
            status=CheckStatus.FAIL,
            message=f"Registry file '{ctx.participants_file}' not found.",
        )

    try:
        with open(ctx.participants_file, "r", encoding="utf-8") as pf:
            pdata = json.load(pf)
    except Exception as e:
        return CheckResult(
            name="participant_registration",
            status=CheckStatus.FAIL,
            message=f"Failed to read participants registry: {e}",
        )

    user_key = ctx.student_login.lower()
    participants = pdata.get("participants", {})
    user_entry = participants.get(user_key)

    if not user_entry:
        is_approved = False
    else:
        status_val = user_entry.get("status", "approved")
        is_approved = status_val in ("approved", None, "")

    if not is_approved:
        comment_md = (
            f"> ⛔ **Evaluation Aborted: Unregistered Competitor**\n\n"
            f"Hello @{ctx.student_login}!\n\n"
            f"Your pull request was not evaluated because your GitHub username is not on the verified participant list for **Ocean Regatta 2026**.\n\n"
            f"To prevent unauthorized resource consumption on our simulation servers, automated evaluations run exclusively for registered competitors.\n\n"
            f"### 📝 How to Register:\n"
            f"1. Visit the [Registration Guide on ocean-regatta.github.io](https://ocean-regatta.github.io/register/).\n"
            f"2. Open a [Competitor Registration Request](https://github.com/{ctx.repo}/issues/new?template=registration_request.yml&title=%5BRegistration%5D%3A+%40{ctx.student_login}&github_username={ctx.student_login}) issue.\n"
            f"3. Once approved by the organizers, simply push a new commit or close & reopen this PR to launch your evaluation run.\n\n"
            f"*(If your team is registered under a different handle, please notify the organizers)*"
        )
        return CheckResult(
            name="participant_registration",
            status=CheckStatus.FAIL,
            message=f"Competitor @{ctx.student_login} is not registered or approved.",
            comment_markdown=comment_md,
            labels_to_add=["unregistered"],
        )

    # Resolve display and team names for subsequent workflow steps
    display_name = user_entry.get("display_name") or user_entry.get("team") or ctx.student_login
    team_name = user_entry.get("team") or ctx.student_login
    user_edition = user_entry.get("edition") or ""

    ctx.display_name = display_name
    ctx.team_name = team_name
    ctx.user_edition = user_edition

    return CheckResult(
        name="participant_registration",
        status=CheckStatus.PASS,
        message=f"Competitor @{ctx.student_login} ('{display_name}') is registered and approved.",
        labels_to_remove=["unregistered"],
        env_vars={
            "DISPLAY_NAME": display_name,
            "TEAM_NAME": team_name,
            "USER_EDITION": user_edition,
        },
    )


def check_submission_window_rule(ctx: SubmissionContext) -> CheckResult:
    """Verifies that the submission occurs within the active competition window."""
    if ctx.force_eval:
        return CheckResult(
            name="submission_window",
            status=CheckStatus.SKIPPED,
            message="Force evaluation flag detected ([force-eval]). Skipping window check.",
        )

    if not os.path.exists(ctx.editions_file):
        return CheckResult(
            name="submission_window",
            status=CheckStatus.SKIPPED,
            message=f"Editions file '{ctx.editions_file}' not found. Skipping window check.",
        )

    target_edition = ctx.user_edition or ctx.regatta_edition or "2026"

    try:
        window_res = check_submission_window(
            editions_file=ctx.editions_file,
            submission_time_input=ctx.submission_time,
            edition_key=target_edition,
            username=ctx.student_login,
            display_name=ctx.display_name,
            team_name=ctx.team_name,
            participants_file=ctx.participants_file,
        )
    except Exception as e:
        return CheckResult(
            name="submission_window",
            status=CheckStatus.FAIL,
            message=f"Submission window validation error: {e}",
        )

    if window_res.get("status") == "within_window":
        return CheckResult(
            name="submission_window",
            status=CheckStatus.PASS,
            message=f"Submission within window for edition '{target_edition}'.",
            labels_to_remove=["submission-too-early", "submission-closed", "submission-rejected"],
            metadata=window_res,
        )

    status_str = window_res.get("status")
    label_to_add = "submission-rejected"
    if status_str == "too_early":
        label_to_add = "submission-too-early"
    elif status_str == "too_late":
        label_to_add = "submission-closed"

    return CheckResult(
        name="submission_window",
        status=CheckStatus.FAIL,
        message=window_res.get("message", "Submission rejected outside allowed competition window."),
        comment_markdown=window_res.get("comment_markdown"),
        labels_to_add=[label_to_add],
        metadata=window_res,
    )


def check_evaluation_cooldown(ctx: SubmissionContext, gh_client: GitHubClient) -> CheckResult:
    """Verifies that the competitor has waited out the cooldown period between runs."""
    if ctx.cooldown_seconds <= 0:
        return CheckResult(
            name="cooldown",
            status=CheckStatus.SKIPPED,
            message=f"Cooldown disabled (COOLDOWN_SECONDS={ctx.cooldown_seconds}). Skipping.",
        )

    if ctx.force_eval:
        return CheckResult(
            name="cooldown",
            status=CheckStatus.SKIPPED,
            message="Force evaluation flag detected ([force-eval]). Skipping cooldown check.",
        )

    if not gh_client.is_active():
        return CheckResult(
            name="cooldown",
            status=CheckStatus.PASS,
            message="GitHub API inactive (dry-run or no token). Cooldown assumed satisfied.",
        )

    last_run_dt = gh_client.get_last_completed_run_time("evaluate.yml", ctx.pr_number)
    if not last_run_dt:
        return CheckResult(
            name="cooldown",
            status=CheckStatus.PASS,
            message="No prior completed evaluation run found for this PR. Cooldown satisfied.",
        )

    now = datetime.now(timezone.utc)
    diff_seconds = (now - last_run_dt).total_seconds()

    if diff_seconds < ctx.cooldown_seconds and diff_seconds >= 0:
        remaining_min = max(1, int(round((ctx.cooldown_seconds - diff_seconds) / 60.0)))
        elapsed_min = max(0, int(round(diff_seconds / 60.0)))

        comment_md = (
            f"### ⏳ Evaluation rejected: cooldown active\n\n"
            f"Your last evaluation occurred **{elapsed_min} minute(s)** ago.\n\n"
            f"To prevent random seed overfitting, please wait **{remaining_min} more minute(s)** before submitting a new commit.\n\n"
            f"*(Tip for instructors/testing: add `[force-eval]` in the PR title to bypass)*"
        )
        return CheckResult(
            name="cooldown",
            status=CheckStatus.FAIL,
            message=f"Cooldown active: {remaining_min} minute(s) remaining.",
            comment_markdown=comment_md,
            metadata={"diff_seconds": diff_seconds, "remaining_min": remaining_min},
        )

    return CheckResult(
        name="cooldown",
        status=CheckStatus.PASS,
        message=f"Cooldown satisfied ({int(diff_seconds // 60)} min elapsed since last run).",
    )


# ==============================================================================
# PIPELINE RUNNER
# ==============================================================================

ACTIVE_CHECKS = [
    ("Target Branch", check_submission_target),
    ("Participant Registration", check_participant_registration),
    ("Submission Window", check_submission_window_rule),
]


def export_github_env(env_vars: Dict[str, str]) -> None:
    """Exports key-value pairs to the GitHub Actions runner environment file."""
    env_file = os.environ.get("GITHUB_ENV")
    if not env_file or not os.path.exists(env_file):
        return

    with open(env_file, "a", encoding="utf-8") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")


def run_all_checks(ctx: SubmissionContext, gh_client: GitHubClient) -> Tuple[bool, List[CheckResult]]:
    """Runs all registered pre-checks sequentially."""
    print("=" * 70)
    print(" Ocean Regatta - Submission Pre-Checks Gatekeeper")
    print(f" Competitor: @{ctx.student_login} | PR #{ctx.pr_number}")
    if ctx.force_eval:
        print(" [force-eval] bypass flag detected in PR metadata")
    print("=" * 70)

    results: List[CheckResult] = []

    # 1. Run basic registered checks
    for check_name, check_fn in ACTIVE_CHECKS:
        res = check_fn(ctx)
        results.append(res)
        print(f"[{res.status.value:<7}] {check_name}: {res.message}")

        if not res.passed:
            # First failing check aborts pipeline
            _handle_failure(ctx, gh_client, res)
            return False, results

    # 2. Run cooldown check (requires gh_client)
    cooldown_res = check_evaluation_cooldown(ctx, gh_client)
    results.append(cooldown_res)
    print(f"[{cooldown_res.status.value:<7}] Evaluation Cooldown: {cooldown_res.message}")
    if not cooldown_res.passed:
        _handle_failure(ctx, gh_client, cooldown_res)
        return False, results

    # 3. All checks passed: apply pass actions
    _handle_success(ctx, gh_client, results)
    return True, results


def _handle_failure(ctx: SubmissionContext, gh_client: GitHubClient, failure: CheckResult) -> None:
    """Processes failure: posts PR comment, attaches labels, sets GitHub annotation."""
    print(f"\n::error::Pre-check failed ({failure.name}): {failure.message}")

    if failure.comment_markdown and gh_client.is_active():
        gh_client.post_pr_comment(ctx.pr_number, failure.comment_markdown)

    if failure.labels_to_add and gh_client.is_active():
        gh_client.add_labels(ctx.pr_number, failure.labels_to_add)

    for lbl in failure.labels_to_remove:
        if gh_client.is_active():
            gh_client.remove_label(ctx.pr_number, lbl)


def _handle_success(ctx: SubmissionContext, gh_client: GitHubClient, results: List[CheckResult]) -> None:
    """Processes success: cleans up prior rejection labels, applies evaluation labels, exports env."""
    print("\n✅ All pre-checks passed successfully. Proceeding with evaluation.")

    # Collect environment variables to export
    accumulated_env: Dict[str, str] = {
        "DISPLAY_NAME": ctx.display_name,
        "TEAM_NAME": ctx.team_name,
        "USER_EDITION": ctx.user_edition,
    }
    for r in results:
        accumulated_env.update(r.env_vars)
    export_github_env(accumulated_env)

    # Clean up prior rejection labels
    stale_labels = ["unregistered", "submission-too-early", "submission-closed", "submission-rejected"]
    for lbl in stale_labels:
        if gh_client.is_active():
            gh_client.remove_label(ctx.pr_number, lbl)

    # Tag PR as evaluation-only and do-not-merge
    if gh_client.is_active():
        gh_client.add_labels(ctx.pr_number, ["do-not-merge", "evaluation-only"])


def main():
    parser = argparse.ArgumentParser(description="Ocean Regatta Submission Pre-Check Gatekeeper")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "Ocean-Regatta/ocean-regatta-2026-template"))
    parser.add_argument("--pr-number", type=int, default=int(os.environ.get("PR_NUMBER", "0") or "0"))
    parser.add_argument("--username", default=os.environ.get("STUDENT_LOGIN") or os.environ.get("GITHUB_ACTOR", ""))
    parser.add_argument("--base-ref", default=os.environ.get("BASE_REF") or os.environ.get("GITHUB_BASE_REF", "evaluation"))
    parser.add_argument("--head-ref", default=os.environ.get("HEAD_REF") or os.environ.get("GITHUB_HEAD_REF", ""))
    parser.add_argument("--title", default=os.environ.get("PR_TITLE", ""))
    parser.add_argument("--body", default=os.environ.get("PR_BODY", ""))
    parser.add_argument("--submission-time", default=os.environ.get("PR_UPDATED_AT") or os.environ.get("PR_CREATED_AT"))
    parser.add_argument("--cooldown", type=int, default=int(os.environ.get("COOLDOWN_SECONDS", "3600") or "3600"))
    parser.add_argument("--edition", default=os.environ.get("REGATTA_EDITION", "2026"))
    parser.add_argument("--participants-file", default=os.environ.get("PARTICIPANTS_FILE", "participants.json"))
    parser.add_argument("--editions-file", default=os.environ.get("EDITIONS_FILE", "editions.json"))
    parser.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    parser.add_argument("--dry-run", action="store_true", help="Do not call GitHub API or post comments/labels")
    parser.add_argument("--json-output", help="Write structured results to JSON file")

    args = parser.parse_args()

    # Dry-run if explicitly requested or if no token available
    is_dry_run = args.dry_run or not bool(args.token)

    ctx = SubmissionContext(
        repo=args.repo,
        pr_number=args.pr_number,
        student_login=args.username,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        pr_title=args.title,
        pr_body=args.body,
        submission_time_input=args.submission_time,
        cooldown_seconds=args.cooldown,
        regatta_edition=args.edition,
        participants_file=args.participants_file,
        editions_file=args.editions_file,
        gh_token=args.token,
        dry_run=is_dry_run,
    )

    gh_client = GitHubClient(repo=args.repo, token=args.token, dry_run=is_dry_run)

    success, results = run_all_checks(ctx, gh_client)

    if args.json_output:
        try:
            with open(args.json_output, "w", encoding="utf-8") as jf:
                json.dump({
                    "passed": success,
                    "student_login": ctx.student_login,
                    "pr_number": ctx.pr_number,
                    "results": [r.to_dict() for r in results],
                }, jf, indent=2)
        except Exception as e:
            print(f"Warning: Failed to write JSON output: {e}", file=sys.stderr)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
