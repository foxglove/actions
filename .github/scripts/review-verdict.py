#!/usr/bin/env python3
"""Exit 0 when beefcake's review on this commit is LGTM.

The workflow runs this after a review is submitted. Exit 0 when the latest
matching review body is LGTM, so the job stays green. Exit 2 when that review
is not visible yet, so the job can wait. Exit 1 for any other verdict, or for
input the job cannot trust. Exit 1 fails the job, so GitHub shows a failed check.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any

LGTM = "LGTM"
# Local beefcake appends this hidden marker after the verdict text.
BEEFCAKE_MARKER = re.compile(r"<!--\s*beefcake-review\s*-->")
# Dismissed and pending reviews are not a submitted verdict.
SKIPPED_STATES = {"PENDING", "DISMISSED"}
EXIT_LGTM = 0
EXIT_NOT_LGTM = 1
EXIT_MISSING = 2


def load_json_values(text: str) -> list[Any]:
    """Parse one JSON value, or several values concatenated in one file."""
    decoder = json.JSONDecoder()
    index = 0
    length = len(text)
    values: list[Any] = []
    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            break
        value, end = decoder.raw_decode(text, index)
        values.append(value)
        index = end
    return values


def flatten_reviews(values: list[Any]) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    for value in values:
        if isinstance(value, list):
            reviews.extend(item for item in value if isinstance(item, dict))
            continue
        if isinstance(value, dict) and isinstance(value.get("id"), int):
            reviews.append(value)
    return reviews


def parse_time(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def job_started_at(jobs_payload: dict[str, Any], job_name: str) -> str | None:
    """Return the start time of this job from the Actions jobs payload."""
    jobs = jobs_payload.get("jobs")
    if not isinstance(jobs, list):
        return None
    suffix = f" / {job_name}"
    started: list[str] = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        name = job.get("name")
        if not isinstance(name, str):
            continue
        if name != job_name and not name.endswith(suffix):
            continue
        value = job.get("started_at")
        if isinstance(value, str) and value.strip():
            started.append(value)
    if not started:
        return None
    return sorted(started)[-1]


def verdict_text(body: str) -> str:
    """Return the review body with the hidden beefcake marker removed."""
    return BEEFCAKE_MARKER.sub("", body).strip()


def one_line(text: str, limit: int = 180) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def review_verdict(
    reviews: list[dict[str, Any]],
    head_sha: str,
    bot_login: str,
    started_at: str,
) -> tuple[str, str]:
    """Return (lgtm|not-lgtm|missing|invalid, message)."""
    started = parse_time(started_at)
    if started is None:
        return ("invalid", "Could not read the start time for this job.")

    candidates: list[dict[str, Any]] = []
    for review in reviews:
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if login != bot_login:
            continue
        if review.get("commit_id") != head_sha:
            continue
        state = review.get("state")
        if not isinstance(state, str) or state in SKIPPED_STATES:
            continue
        submitted_raw = review.get("submitted_at")
        if not isinstance(submitted_raw, str):
            continue
        submitted = parse_time(submitted_raw)
        if submitted is None or submitted < started:
            continue
        candidates.append(review)

    if not candidates:
        return ("missing", "Beefcake did not post a review on this commit.")

    def sort_key(review: dict[str, Any]) -> tuple[datetime, int]:
        submitted = parse_time(str(review.get("submitted_at")))
        # Candidates already have a parseable submitted_at.
        submitted_at = submitted if submitted is not None else started
        review_id = review.get("id")
        numeric_id = review_id if isinstance(review_id, int) else 0
        return (submitted_at, numeric_id)

    latest = max(candidates, key=sort_key)
    body = latest.get("body")
    text = verdict_text(body) if isinstance(body, str) else ""
    if text == LGTM:
        return ("lgtm", "The beefcake review on this commit is LGTM.")
    if text == "":
        shown = "empty"
    else:
        shown = one_line(text)
    return (
        "not-lgtm",
        f"The beefcake review on this commit is not LGTM. The review body is: {shown}",
    )


def verdict_from_files(
    jobs_text: str,
    job_name: str,
    reviews_text: str,
    head_sha: str,
    bot_login: str,
) -> tuple[str, str]:
    try:
        job_values = load_json_values(jobs_text)
        review_values = load_json_values(reviews_text)
    except json.JSONDecodeError:
        return ("invalid", "Could not read the review response from GitHub.")
    if len(job_values) != 1 or not isinstance(job_values[0], dict):
        return ("invalid", "Could not read the jobs response from GitHub.")
    started_at = job_started_at(job_values[0], job_name)
    if started_at is None:
        return ("invalid", f"Could not read the start time for job {job_name}.")
    reviews = flatten_reviews(review_values)
    # An empty page is a valid list. An error object or empty file is not.
    pages_are_lists = all(isinstance(value, list) for value in review_values)
    if not review_values or (not reviews and not pages_are_lists):
        return ("invalid", "Could not read the reviews response from GitHub.")
    return review_verdict(reviews, head_sha, bot_login, started_at)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fail unless the beefcake review body is LGTM.")
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--bot", required=True)
    args = parser.parse_args(argv)
    with open(args.jobs, encoding="utf-8") as jobs_file:
        jobs_text = jobs_file.read()
    with open(args.reviews, encoding="utf-8") as reviews_file:
        reviews_text = reviews_file.read()
    status, message = verdict_from_files(
        jobs_text,
        args.job_name,
        reviews_text,
        args.head_sha,
        args.bot,
    )
    print(message)
    if status == "lgtm":
        return EXIT_LGTM
    if status == "missing":
        return EXIT_MISSING
    return EXIT_NOT_LGTM


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
