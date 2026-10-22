#!/usr/bin/env python3
"""Exit 0 unless beefcake posted a Blocker or Should fix.

The workflow runs this after a review is submitted. Exit 0 when the review
body or a review comment is LGTM, when the only comments are nits, or when a
summary body has no unresolved Blocker or Should fix thread. Exit 2 when that
review is not visible yet, so the job can wait. Exit 1 when a Blocker or
Should fix is present, or when the input cannot be trusted. Exit 1 fails the
job, so GitHub shows a failed check.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from typing import Any

LGTM = "LGTM"
SUMMARY_BODY = "Prior unresolved thread(s) still open."
# Local beefcake appends this hidden marker after the verdict text.
BEEFCAKE_MARKER = re.compile(r"<!--\s*beefcake-review\s*-->")
# These labels fail the check. A nit does not.
FAILING_LABELS = ("Blocker:", "Should fix:")
# Dismissed and pending reviews are not a submitted verdict.
SKIPPED_STATES = {"PENDING", "DISMISSED"}
# GraphQL omits the [bot] suffix that the REST API includes.
REVIEW_BOTS = {"foxglove-beefcake", "claude"}
EXIT_PASS = 0
EXIT_FAIL = 1
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


def canonical_login(login: str) -> str:
    if login.endswith("[bot]"):
        return login[: -len("[bot]")]
    return login


def is_review_bot(login: str | None, bot_login: str) -> bool:
    """True for this run's bot and for earlier beefcake or claude reviews."""
    if login is None:
        return False
    return canonical_login(login) in REVIEW_BOTS | {canonical_login(bot_login)}


def accepted_logins(bot_login: str) -> set[str]:
    """Return the review-bot logins this check should treat as its own.

    One login is the normal case. A comma-separated list lets a rerun accept
    an LGTM from either foxglove-beefcake or claude before the job knows which
    bot posted it.
    """
    return {canonical_login(part.strip()) for part in bot_login.split(",") if part.strip()}


def same_bot(login: str | None, bot_login: str) -> bool:
    if login is None:
        return False
    return canonical_login(login) in accepted_logins(bot_login)


def comment_login(comment: dict[str, Any]) -> str | None:
    user = comment.get("user")
    if isinstance(user, dict) and isinstance(user.get("login"), str):
        return user["login"]
    author = comment.get("author")
    if isinstance(author, dict) and isinstance(author.get("login"), str):
        return author["login"]
    return None


def is_lgtm_text(body: object) -> bool:
    """True when the text is exactly LGTM after the hidden marker is removed."""
    if not isinstance(body, str):
        return False
    return verdict_text(body) == LGTM


def is_verdict_body(body: object) -> bool:
    """True when the review body is LGTM or the unresolved-thread summary."""
    if not isinstance(body, str):
        return False
    text = verdict_text(body)
    return text == LGTM or text == SUMMARY_BODY


def is_reply_comment(comment: dict[str, Any]) -> bool:
    return comment.get("in_reply_to_id") is not None or comment.get("in_reply_to") is not None


def is_reply_only_review(
    review: dict[str, Any],
    comments: list[dict[str, Any]],
    bot_login: str,
) -> bool:
    """True when this review only carries thread replies and has no verdict body.

    GitHub files each thread reply on a new review. That review uses the head
    commit and a later submitted time, but it is not a new verdict. A reply
    whose text is LGTM is a verdict, so that review stays in consideration.
    """
    if is_verdict_body(review.get("body")):
        return False
    review_id = review.get("id")
    owned = [
        item for item in comments if item.get("pull_request_review_id") == review_id
    ]
    if not owned:
        return False
    for item in owned:
        if same_bot(comment_login(item), bot_login) and is_lgtm_text(item.get("body")):
            return False
    return all(is_reply_comment(item) for item in owned)


def failing_label(body: object) -> str | None:
    """Return Blocker or Should fix when the comment starts with that label."""
    if not isinstance(body, str):
        return None
    text = BEEFCAKE_MARKER.sub("", body).lstrip()
    for label in FAILING_LABELS:
        if text.startswith(label):
            return label
    return None


def review_sort_key(review: dict[str, Any], started: datetime) -> tuple[datetime, int]:
    submitted = parse_time(str(review.get("submitted_at")))
    submitted_at = submitted if submitted is not None else started
    review_id = review.get("id")
    numeric_id = review_id if isinstance(review_id, int) else 0
    return (submitted_at, numeric_id)


def root_comments_for_review(
    comments: list[dict[str, Any]],
    review_id: int,
    bot_login: str,
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for comment in comments:
        if comment.get("pull_request_review_id") != review_id:
            continue
        if is_reply_comment(comment):
            continue
        if not same_bot(comment_login(comment), bot_login):
            continue
        matched.append(comment)
    return matched


def thread_roots(threads: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return unresolved threads paired with their first comment."""
    roots: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for thread in threads:
        if thread.get("isResolved") is True:
            continue
        comments = thread.get("comments")
        nodes: object
        if isinstance(comments, list):
            nodes = comments
        elif isinstance(comments, dict):
            nodes = comments.get("nodes")
        else:
            continue
        if not isinstance(nodes, list) or not nodes or not isinstance(nodes[0], dict):
            continue
        roots.append((thread, nodes[0]))
    return roots


def review_has_lgtm_comment(
    comments: list[dict[str, Any]],
    review_id: int,
    bot_login: str,
) -> bool:
    """True when this review has a bot comment whose text is LGTM."""
    for comment in comments:
        if comment.get("pull_request_review_id") != review_id:
            continue
        if not same_bot(comment_login(comment), bot_login):
            continue
        if is_lgtm_text(comment.get("body")):
            return True
    return False


def issue_comment_is_lgtm(
    comments: list[dict[str, Any]],
    bot_login: str,
    started: datetime,
) -> bool:
    """True when the bot posted an LGTM conversation comment during this job.

    Conversation comments are not tied to a commit. Only one posted at or
    after the job start counts, so an older LGTM cannot pass a later commit.
    """
    for comment in comments:
        if not same_bot(comment_login(comment), bot_login):
            continue
        if not is_lgtm_text(comment.get("body")):
            continue
        created_raw = comment.get("created_at")
        if not isinstance(created_raw, str):
            continue
        created = parse_time(created_raw)
        if created is None or created < started:
            continue
        return True
    return False


def failing_thread_message(
    threads: list[dict[str, Any]],
    bot_login: str,
) -> str | None:
    """Return the failure message for an unresolved Blocker or Should fix thread."""
    for _thread, root in thread_roots(threads):
        if not is_review_bot(comment_login(root), bot_login):
            continue
        label = failing_label(root.get("body"))
        if label is None:
            continue
        shown = one_line(verdict_text(str(root.get("body"))))
        return f"The beefcake review on this commit has an unresolved {label} thread. {shown}"
    return None


def review_verdict(
    reviews: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    threads: list[dict[str, Any]],
    head_sha: str,
    bot_login: str,
    started_at: str,
    issue_comments: list[dict[str, Any]] | None = None,
    accept_earlier: bool = False,
) -> tuple[str, str]:
    """Return (pass|fail|missing|invalid, message)."""
    started = parse_time(started_at)
    if started is None:
        return ("invalid", "Could not read the start time for this job.")

    # A rerun starts after the LGTM was posted. Count reviews from before this
    # attempt so that LGTM can turn the original pull_request check green.
    # Conversation comments stay tied to this job's start either way.
    issue_lgtm = False
    if not accept_earlier:
        issue_lgtm = issue_comment_is_lgtm(issue_comments or [], bot_login, started)

    candidates: list[dict[str, Any]] = []
    for review in reviews:
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if not same_bot(login, bot_login):
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
        if submitted is None or (not accept_earlier and submitted < started):
            continue
        if is_reply_only_review(review, comments, bot_login):
            continue
        candidates.append(review)

    if not candidates:
        if not issue_lgtm:
            return ("missing", "Beefcake did not post a review on this commit.")
        thread_failure = failing_thread_message(threads, bot_login)
        if thread_failure is not None:
            return ("fail", thread_failure)
        return ("pass", "The beefcake review on this commit is LGTM.")

    latest = max(candidates, key=lambda review: review_sort_key(review, started))
    latest_id = latest.get("id")
    if not isinstance(latest_id, int):
        return ("invalid", "Could not read the id of the beefcake review.")
    body = latest.get("body")
    text = verdict_text(body) if isinstance(body, str) else ""
    latest_comments = root_comments_for_review(comments, latest_id, bot_login)
    comment_lgtm = review_has_lgtm_comment(comments, latest_id, bot_login)
    # An empty body means the review added comments. Wait until those comments appear.
    if text == "" and not latest_comments and not comment_lgtm:
        return ("missing", "Beefcake posted a review, and its comments are not visible yet.")

    for comment in latest_comments:
        label = failing_label(comment.get("body"))
        if label is None:
            continue
        shown = one_line(verdict_text(str(comment.get("body"))))
        return (
            "fail",
            f"The beefcake review on this commit has a {label} comment. {shown}",
        )

    thread_failure = failing_thread_message(threads, bot_login)
    if thread_failure is not None:
        return ("fail", thread_failure)

    if text == LGTM or comment_lgtm or issue_lgtm:
        return ("pass", "The beefcake review on this commit is LGTM.")
    return ("pass", "The beefcake review on this commit has no Blocker or Should fix.")


def flatten_threads(values: list[Any]) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    for value in values:
        if isinstance(value, list):
            threads.extend(item for item in value if isinstance(item, dict))
            continue
        if not isinstance(value, dict):
            continue
        nested = value.get("threads")
        if isinstance(nested, list):
            threads.extend(item for item in nested if isinstance(item, dict))
            continue
        if "isResolved" in value or "comments" in value:
            threads.append(value)
    return threads


def list_payload(values: list[Any], flatten) -> list[dict[str, Any]] | None:
    """Return items from a JSON list payload. None means the payload is unusable."""
    items = flatten(values)
    pages_are_lists = all(isinstance(value, list) for value in values)
    if not values or (not items and not pages_are_lists):
        return None
    return items


def verdict_from_files(
    jobs_text: str,
    job_name: str,
    reviews_text: str,
    head_sha: str,
    bot_login: str,
    comments_text: str = "[]",
    threads_text: str = "[]",
    issue_comments_text: str = "[]",
    accept_earlier: bool = False,
) -> tuple[str, str]:
    try:
        job_values = load_json_values(jobs_text)
        review_values = load_json_values(reviews_text)
        comment_values = load_json_values(comments_text)
        thread_values = load_json_values(threads_text)
        issue_values = load_json_values(issue_comments_text)
    except json.JSONDecodeError:
        return ("invalid", "Could not read the review response from GitHub.")
    if len(job_values) != 1 or not isinstance(job_values[0], dict):
        return ("invalid", "Could not read the jobs response from GitHub.")
    started_at = job_started_at(job_values[0], job_name)
    if started_at is None:
        return ("invalid", f"Could not read the start time for job {job_name}.")
    reviews = list_payload(review_values, flatten_reviews)
    comments = list_payload(comment_values, flatten_reviews)
    threads = list_payload(thread_values, flatten_threads)
    issue_comments = list_payload(issue_values, flatten_reviews)
    if reviews is None or comments is None or threads is None or issue_comments is None:
        return ("invalid", "Could not read the reviews response from GitHub.")
    return review_verdict(
        reviews,
        comments,
        threads,
        head_sha,
        bot_login,
        started_at,
        issue_comments,
        accept_earlier,
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fail unless the beefcake review body is LGTM.")
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--comments", required=True)
    parser.add_argument("--threads", required=True)
    parser.add_argument("--issue-comments")
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--bot", required=True)
    parser.add_argument(
        "--accept-earlier",
        action="store_true",
        help="Count a review posted before this job started.",
    )
    args = parser.parse_args(argv)
    with open(args.jobs, encoding="utf-8") as jobs_file:
        jobs_text = jobs_file.read()
    with open(args.reviews, encoding="utf-8") as reviews_file:
        reviews_text = reviews_file.read()
    with open(args.comments, encoding="utf-8") as comments_file:
        comments_text = comments_file.read()
    with open(args.threads, encoding="utf-8") as threads_file:
        threads_text = threads_file.read()
    if args.issue_comments:
        with open(args.issue_comments, encoding="utf-8") as issue_comments_file:
            issue_comments_text = issue_comments_file.read()
    else:
        issue_comments_text = "[]"
    status, message = verdict_from_files(
        jobs_text,
        args.job_name,
        reviews_text,
        args.head_sha,
        args.bot,
        comments_text,
        threads_text,
        issue_comments_text,
        args.accept_earlier,
    )
    print(message)
    if status == "pass":
        return EXIT_PASS
    if status == "missing":
        return EXIT_MISSING
    return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
