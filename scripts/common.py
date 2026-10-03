"""Shared definitions for the app pilot. Decisions here are fixed before results."""

from __future__ import annotations

import re
from datetime import datetime, timezone

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
