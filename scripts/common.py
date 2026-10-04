"""Shared definitions for the app pilot. Decisions here are fixed before results."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WINDOW_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 10, 1, tzinfo=timezone.utc)  # exclusive; cohort is Apr 1–Sep 30
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]

# Primary bot. GraphQL login is "claude"; REST login is "claude[bot]".
BOT_LOGINS = {"claude"}

# Word-boundary, case-sensitive, per the study definition ("containing LGTM").
LGTM_RE = re.compile(r"(?<![A-Za-z0-9])LGTM(?![A-Za-z0-9])")

REQUIRED_CHECKS = [
    "lint",
    "docker-build",
    "tsc",
    "test (API)",
    "test (app)",
    "yarn (windows)",
    "build-foxglove-extension-pkg",
    "test-self-hosted-api",
    "build-foxglove-embed-pkg",
    "superadmin-storybook",
    "Storybook / app screenshots",
    "quick-checks",
    "generate-layout-api-python-classes",
    "test (e2e-desktop)",
    "test (e2e-web)",
    "build-self-hosted-app",
]

# Job-backed checks vs commit-status checks. integration_id 15368 is GitHub Actions,
# but this token cannot read the Checks API. Status contexts are read from the
# Statuses API; job names are read from the Actions workflow-runs API.
STATUS_CHECKS = {"Storybook / app screenshots"}
JOB_CHECKS = [c for c in REQUIRED_CHECKS if c not in STATUS_CHECKS]

WORKFLOW_FOR_JOB = {
    "lint": ".github/workflows/ci.yml",
    "docker-build": ".github/workflows/ci.yml",
    "tsc": ".github/workflows/ci.yml",
    "test (API)": ".github/workflows/ci.yml",
    "test (app)": ".github/workflows/ci.yml",
    "yarn (windows)": ".github/workflows/ci.yml",
    "build-foxglove-extension-pkg": ".github/workflows/ci.yml",
    "test-self-hosted-api": ".github/workflows/ci.yml",
    "build-foxglove-embed-pkg": ".github/workflows/ci.yml",
    "quick-checks": ".github/workflows/ci.yml",
    "generate-layout-api-python-classes": ".github/workflows/ci.yml",
    "build-self-hosted-app": ".github/workflows/ci.yml",
    "superadmin-storybook": ".github/workflows/storybook.yml",
    "test (e2e-desktop)": ".github/workflows/playwright.yml",
    "test (e2e-web)": ".github/workflows/playwright.yml",
}

ACK_RE = re.compile(
    r"\b(good catch|nice catch|great catch|fixed|will fix|i'?ll fix|addressed|done|you(?:'| a)?re right|good point|oops)\b",
    re.I,
)

FIX_TITLE_RE = re.compile(
    r"\b(fix(?:es)?|hotfix(?:es)?|regression|revert(?:s|ed)?)\b",
    re.I,
)
PR_REF_RE = re.compile(r"(?:#|pull/)(\d{3,6})\b")

# Tenure buckets, chosen before looking at the distribution.
def tenure_bucket(days: float | None) -> str:
    if days is None:
        return "unknown"
    if days < 180:
        return "<6mo"
    if days < 730:
        return "6-24mo"
    return "2y+"


def size_bucket(lines: int) -> str:
    if lines < 50:
        return "XS"
    if lines < 200:
        return "S"
    if lines < 500:
        return "M"
    if lines < 1000:
        return "L"
    return "XL"


SIZE_ORDER = ["XS", "S", "M", "L", "XL"]
TENURE_ORDER = ["<6mo", "6-24mo", "2y+", "unknown"]


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hours_between(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return (b - a).total_seconds() / 3600.0


def month_key(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def month_index(key: str) -> int:
    """April 2026 = 0 … September 2026 = 5. Pre-registered continuous coding."""
    year, month = int(key[:4]), int(key[5:7])
    return (year - 2026) * 12 + (month - 4)


def norm_login(login: str | None) -> str | None:
    if not login:
        return None
    if login.endswith("[bot]"):
        return login[: -len("[bot]")]
    return login


def is_bot_author(author: dict | None) -> bool:
    if not author:
        return False
    if author.get("__typename") == "Bot":
        return True
    login = author.get("login") or ""
    return login.endswith("[bot]") or norm_login(login) in BOT_LOGINS


def is_review_bot(author: dict | None) -> bool:
    if not author:
        return False
    return norm_login(author.get("login")) in BOT_LOGINS


def contains_lgtm(body: str | None) -> bool:
    if not body:
        return False
    return LGTM_RE.search(body) is not None


# A-ci only when the comment itself names CI. A path like "latest" or "tests/" is not evidence.
CI_REF_RE = re.compile(r"\b(ci|tests?|lint|typecheck|tsc|failing check)\b", re.I)


def _connection_nodes(pr: dict, field: str) -> list:
    return ((pr.get(field) or {}).get("nodes") or [])


def pr_commits(pr: dict) -> list[dict]:
    rows = []
    for node in _connection_nodes(pr, "commits"):
        commit = node.get("commit") or {}
        sha = commit.get("oid")
        at = parse_ts(commit.get("committedDate") or commit.get("authoredDate"))
        if sha and at:
            rows.append({"sha": sha, "at": at})
    rows.sort(key=lambda row: row["at"])
    return rows


def bot_lgtm_events(pr: dict) -> list[dict]:
    """Earliest-first bot LGTM events from reviews, issue comments, and review threads.

    Comment events have no commit SHA. Callers fill that with the last commit at or
    before the comment. This is the single definition of "first bot LGTM".
    """
    events = []
    for rev in _connection_nodes(pr, "reviews"):
        if not is_review_bot(rev.get("author")):
            continue
        body = rev.get("body") or ""
        if contains_lgtm(body):
            events.append(
                {
                    "at": parse_ts(rev.get("submittedAt")),
                    "sha": (rev.get("commit") or {}).get("oid"),
                    "kind": "review",
                    "exact": body.strip() == "LGTM",
                    "body": body,
                    "database_id": rev.get("databaseId"),
                }
            )
    for comment in _connection_nodes(pr, "comments"):
        if not is_review_bot(comment.get("author")):
            continue
        body = comment.get("body") or ""
        if contains_lgtm(body):
            events.append(
                {
                    "at": parse_ts(comment.get("createdAt")),
                    "sha": None,
                    "kind": "issue_comment",
                    "exact": body.strip() == "LGTM",
                    "body": body,
                    "database_id": comment.get("databaseId"),
                }
            )
    for thread in _connection_nodes(pr, "reviewThreads"):
        for comment in ((thread.get("comments") or {}).get("nodes") or []):
            if not is_review_bot(comment.get("author")):
                continue
            body = comment.get("body") or ""
            if contains_lgtm(body):
                events.append(
                    {
                        "at": parse_ts(comment.get("createdAt")),
                        "sha": None,
                        "kind": "review_comment",
                        "exact": body.strip() == "LGTM",
                        "body": body,
                        "database_id": comment.get("databaseId"),
                        "path": comment.get("path"),
                    }
                )
    events = [event for event in events if event["at"] is not None]
    events.sort(key=lambda event: event["at"])
    return events


def first_lgtm_sha(pr: dict) -> str | None:
    events = bot_lgtm_events(pr)
    if not events:
        return None
    first = events[0]
    if first.get("sha"):
        return first["sha"]
    prior = [row["sha"] for row in pr_commits(pr) if row["at"] <= first["at"]]
    if prior:
        return prior[-1]
    # A rebase rewrites committedDate, so every commit can fall after the comment.
    # The current head is then later than the LGTM. Do not score CI on it.
    return None


def load_ci_index(eval_dir: Path) -> dict[int, dict]:
    """CI-at-LGTM rows. no_lgtm files and empty SHA lists are not mergeable=false."""
    out: dict[int, dict] = {}
    if not eval_dir.exists():
        return out
    for path in eval_dir.glob("*.json"):
        if not path.stem.isdigit():
            continue
        data = json.loads(path.read_text())
        shas = data.get("shas") or []
        ci_known = (
            bool(shas)
            and not data.get("no_lgtm")
            and not data.get("sha_unknown")
            and not data.get("fetch_error")
        )
        chosen = None
        mergeable = False
        first_eval = None
        for ev in data.get("evals") or []:
            if first_eval is None:
                first_eval = ev
            if ev.get("passed"):
                chosen = ev.get("sha")
                mergeable = bool(shas) and ev.get("sha") == shas[0]
                break
        if chosen is None and shas:
            chosen = shas[0]
        out[int(data["number"])] = {
            "counterfactual_sha": chosen,
            "sha": chosen,
            "mergeable_at_lgtm": mergeable if ci_known else None,
            "lgtm_sha_failed_checks": (first_eval or {}).get("failed") or [],
            "lgtm_sha_missing_checks": (first_eval or {}).get("missing") or [],
            "lgtm_sha_passed": bool(first_eval and first_eval.get("passed")) if ci_known else None,
            "ci_known": ci_known,
            "sha_unknown": bool(data.get("sha_unknown")),
            "fetch_error": bool(data.get("fetch_error")),
        }
    return out


def study_repo() -> Path:
    return Path(os.environ.get("FOXGLOVE_APP_CLONE", "/tmp/foxglove-app"))


def git_cred_helper() -> str:
    return os.environ.get("STUDY_GIT_CRED", "/tmp/git-cred.sh")


def git_env() -> dict:
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = os.environ.get("STUDY_GIT_CONFIG", "/tmp/empty-gitconfig")
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = os.environ.get("STUDY_GIT_ASKPASS", "/tmp/git-askpass.sh")
    return env


def fetch_prs_running() -> bool:
    """True only while the Python PR fetch is alive.

    A shell wrapper whose argv still contains the script name does not count.
    pgrep anchors at the start of the command line.
    """
    proc = subprocess.run(
        ["pgrep", "-f", r"^python3 ([^ ]*/)?scripts/fetch_prs\.py"],
        capture_output=True,
    )
    return proc.returncode == 0


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    from math import sqrt

    p = k / n
    z2 = z * z
    den = 1 + z2 / n
    center = (p + z2 / (2 * n)) / den
    margin = z * sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / den
    return max(0.0, center - margin), min(1.0, center + margin)


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    rank = (len(xs) - 1) * p
    lo = int(rank)
    hi = min(lo + 1, len(xs) - 1)
    w = rank - lo
    return xs[lo] * (1 - w) + xs[hi] * w
