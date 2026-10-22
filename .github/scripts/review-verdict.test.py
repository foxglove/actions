#!/usr/bin/env python3
"""Tests for the beefcake LGTM check."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("review-verdict.py")
SPEC = importlib.util.spec_from_file_location("review_verdict", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
review_verdict = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review_verdict)

HEAD = "abc123"
BOT = "foxglove-beefcake[bot]"
STARTED = "2026-10-20T12:00:00Z"


def review(
    body: str | None,
    *,
    submitted_at: str = "2026-10-20T12:05:00Z",
    commit_id: str = HEAD,
    login: str = BOT,
    state: str = "COMMENTED",
    review_id: int = 1,
) -> dict:
    return {
        "id": review_id,
        "body": body,
        "commit_id": commit_id,
        "state": state,
        "submitted_at": submitted_at,
        "user": {"login": login},
    }


def jobs(name: str = "review / beefcake", started_at: str = STARTED) -> dict:
    return {"jobs": [{"name": name, "started_at": started_at}]}


def comment(
    body: str,
    *,
    review_id: int = 1,
    login: str = BOT,
    comment_id: int = 10,
    in_reply_to_id: int | None = None,
) -> dict:
    return {
        "id": comment_id,
        "body": body,
        "pull_request_review_id": review_id,
        "in_reply_to_id": in_reply_to_id,
        "user": {"login": login},
    }


def thread(body: str, *, login: str = "foxglove-beefcake", resolved: bool = False) -> dict:
    return {
        "isResolved": resolved,
        "comments": {"nodes": [{"author": {"login": login}, "body": body}]},
    }


class ReviewVerdictTest(unittest.TestCase):
    def decide(
        self,
        reviews: list[dict],
        comments: list[dict] | None = None,
        threads: list[dict] | None = None,
        job_name: str = "beefcake",
        issue_comments: list[dict] | None = None,
        accept_earlier: bool = False,
    ):
        payload = jobs(f"review / {job_name}")
        return review_verdict.verdict_from_files(
            json.dumps(payload),
            job_name,
            json.dumps(reviews),
            HEAD,
            BOT,
            json.dumps(comments or []),
            json.dumps(threads or []),
            json.dumps(issue_comments or []),
            accept_earlier,
        )

    def test_lgtm_passes(self) -> None:
        status, message = self.decide([review("LGTM")])
        self.assertEqual(status, "pass")
        self.assertIn("LGTM", message)

    def test_lgtm_with_surrounding_whitespace_passes(self) -> None:
        status, _message = self.decide([review("\nLGTM\n")])
        self.assertEqual(status, "pass")

    def test_lgtm_with_hidden_marker_passes(self) -> None:
        status, _message = self.decide([review("LGTM\n\n<!-- beefcake-review -->")])
        self.assertEqual(status, "pass")

    def test_approving_review_passes(self) -> None:
        status, message = self.decide([review("LGTM", state="APPROVED")])
        self.assertEqual(status, "pass")
        self.assertIn("is LGTM", message)

    def test_lgtm_review_comment_passes(self) -> None:
        status, message = self.decide([review("")], [comment("LGTM")])
        self.assertEqual(status, "pass")
        self.assertIn("is LGTM", message)

    def test_lgtm_review_comment_with_marker_passes(self) -> None:
        status, message = self.decide(
            [review("")],
            [comment("LGTM\n\n<!-- beefcake-review -->")],
        )
        self.assertEqual(status, "pass")
        self.assertIn("is LGTM", message)

    def test_lgtm_reply_passes(self) -> None:
        status, message = self.decide(
            [review("")],
            [comment("LGTM", in_reply_to_id=9)],
        )
        self.assertEqual(status, "pass")
        self.assertIn("is LGTM", message)

    def test_lgtm_issue_comment_passes(self) -> None:
        status, message = self.decide(
            [],
            issue_comments=[
                {
                    "id": 1,
                    "body": "LGTM\n\n<!-- beefcake-review -->",
                    "created_at": "2026-10-20T12:05:00Z",
                    "user": {"login": BOT},
                }
            ],
        )
        self.assertEqual(status, "pass")
        self.assertIn("is LGTM", message)

    def test_old_issue_comment_lgtm_is_missing(self) -> None:
        status, _message = self.decide(
            [],
            issue_comments=[
                {
                    "id": 1,
                    "body": "LGTM",
                    "created_at": "2026-10-20T11:00:00Z",
                    "user": {"login": BOT},
                }
            ],
        )
        self.assertEqual(status, "missing")

    def test_human_issue_comment_lgtm_is_missing(self) -> None:
        status, _message = self.decide(
            [],
            issue_comments=[
                {
                    "id": 1,
                    "body": "LGTM",
                    "created_at": "2026-10-20T12:05:00Z",
                    "user": {"login": "someone"},
                }
            ],
        )
        self.assertEqual(status, "missing")

    def test_unresolved_should_fix_fails_lgtm_body(self) -> None:
        status, message = self.decide(
            [review("LGTM")],
            [],
            [thread("Should fix: close the file.")],
        )
        self.assertEqual(status, "fail")
        self.assertIn("unresolved Should fix:", message)

    def test_should_fix_fails_when_issue_comment_is_lgtm(self) -> None:
        status, _message = self.decide(
            [review("")],
            [comment("Should fix: close the file.")],
            issue_comments=[
                {
                    "id": 1,
                    "body": "LGTM",
                    "created_at": "2026-10-20T12:05:00Z",
                    "user": {"login": BOT},
                }
            ],
        )
        self.assertEqual(status, "fail")

    def test_accept_earlier_lgtm_passes(self) -> None:
        status, message = self.decide(
            [review("LGTM", submitted_at="2026-10-20T11:00:00Z")],
            accept_earlier=True,
        )
        self.assertEqual(status, "pass")
        self.assertIn("is LGTM", message)

    def test_empty_body_waits_for_comments(self) -> None:
        status, message = self.decide([review("")])
        self.assertEqual(status, "missing")
        self.assertIn("comments", message)

    def test_null_body_waits_for_comments(self) -> None:
        status, _message = self.decide([review(None)])
        self.assertEqual(status, "missing")

    def test_nit_comment_passes_while_unresolved(self) -> None:
        status, message = self.decide(
            [review("")],
            [comment("Nit (optional): rename the local variable.")],
            [thread("Nit (optional): rename the local variable.")],
        )
        self.assertEqual(status, "pass")
        self.assertIn("no Blocker or Should fix", message)

    def test_summary_body_with_unresolved_nit_passes(self) -> None:
        status, _message = self.decide(
            [review("Prior unresolved thread(s) still open.\n\n<!-- beefcake-review -->")],
            [],
            [thread("Nit (optional): rename the local variable.")],
        )
        self.assertEqual(status, "pass")

    def test_summary_body_without_threads_passes(self) -> None:
        status, _message = self.decide([review("Prior unresolved thread(s) still open.")])
        self.assertEqual(status, "pass")

    def test_should_fix_comment_fails(self) -> None:
        status, message = self.decide(
            [review("")],
            [comment("Should fix: the migration drops the column.")],
            [thread("Should fix: the migration drops the column.")],
        )
        self.assertEqual(status, "fail")
        self.assertIn("Should fix:", message)

    def test_blocker_comment_fails(self) -> None:
        status, message = self.decide(
            [review("")],
            [comment("Blocker: the token is written to the log.")],
        )
        self.assertEqual(status, "fail")
        self.assertIn("Blocker:", message)
        self.assertIn("token is written", message)

    def test_unresolved_blocker_thread_fails_summary_body(self) -> None:
        status, message = self.decide(
            [review("Prior unresolved thread(s) still open.")],
            [],
            [thread("Blocker: the token is written to the log.")],
        )
        self.assertEqual(status, "fail")
        self.assertIn("unresolved Blocker:", message)

    def test_resolved_blocker_thread_passes(self) -> None:
        status, _message = self.decide(
            [review("LGTM")],
            [],
            [thread("Blocker: the token is written to the log.", resolved=True)],
        )
        self.assertEqual(status, "pass")

    def test_unresolved_should_fix_from_claude_fails(self) -> None:
        status, _message = self.decide(
            [review("Prior unresolved thread(s) still open.")],
            [],
            [thread("Should fix: close the file.", login="claude")],
        )
        self.assertEqual(status, "fail")

    def test_human_should_fix_thread_does_not_fail(self) -> None:
        status, _message = self.decide(
            [review("LGTM")],
            [],
            [thread("Should fix: rename this.", login="someone")],
        )
        self.assertEqual(status, "pass")

    def test_reply_with_label_does_not_fail(self) -> None:
        status, _message = self.decide(
            [review("")],
            [
                comment("Nit (optional): rename the local variable."),
                comment("Should fix: actually this matters.", comment_id=11, in_reply_to_id=10),
            ],
            [thread("Nit (optional): rename the local variable.")],
        )
        self.assertEqual(status, "pass")

    def test_label_must_be_a_prefix(self) -> None:
        status, _message = self.decide(
            [review("")],
            [comment("See the note. Blocker: this is not the label.")],
        )
        self.assertEqual(status, "pass")

    def test_lowercase_lgtm_passes(self) -> None:
        status, _message = self.decide([review("lgtm")])
        self.assertEqual(status, "pass")

    def test_lgtm_with_extra_text_passes(self) -> None:
        status, _message = self.decide([review("LGTM, with one note")])
        self.assertEqual(status, "pass")

    def test_later_reply_only_review_keeps_lgtm(self) -> None:
        reviews = [
            review("LGTM", submitted_at="2026-10-20T12:05:00Z", review_id=1),
            review("", submitted_at="2026-10-20T12:05:01Z", review_id=2),
        ]
        status, message = self.decide(
            reviews,
            [comment("Resolved.", review_id=2, comment_id=11, in_reply_to_id=99)],
        )
        self.assertEqual(status, "pass")
        self.assertIn("LGTM", message)
        self.assertNotIn("not visible yet", message)

    def test_later_reply_only_review_with_non_verdict_body_keeps_lgtm(self) -> None:
        reviews = [
            review(
                "LGTM\n\n<!-- beefcake-review -->",
                submitted_at="2026-10-20T12:05:00Z",
                review_id=1,
            ),
            review("thanks", submitted_at="2026-10-20T12:05:01Z", review_id=2),
        ]
        status, message = self.decide(
            reviews,
            [comment("Resolved.", review_id=2, comment_id=11, in_reply_to_id=99)],
            [thread("Nit (optional): rename the local variable.")],
        )
        self.assertEqual(status, "pass")
        self.assertIn("LGTM", message)

    def test_latest_should_fix_comment_fails(self) -> None:
        reviews = [
            review("LGTM", submitted_at="2026-10-20T12:05:00Z", review_id=1),
            review("", submitted_at="2026-10-20T12:06:00Z", review_id=2),
        ]
        status, _message = self.decide(
            reviews,
            [comment("Should fix: close the file.", review_id=2, comment_id=20)],
        )
        self.assertEqual(status, "fail")

    def test_latest_lgtm_ignores_earlier_comment_on_another_review(self) -> None:
        reviews = [
            review("", submitted_at="2026-10-20T12:05:00Z", review_id=1),
            review("LGTM", submitted_at="2026-10-20T12:06:00Z", review_id=2),
        ]
        status, _message = self.decide(
            reviews,
            [comment("Should fix: close the file.", review_id=1)],
        )
        self.assertEqual(status, "pass")

    def test_same_timestamp_uses_higher_id(self) -> None:
        reviews = [
            review("LGTM", review_id=1),
            review("", review_id=2),
        ]
        status, _message = self.decide(
            reviews,
            [comment("Blocker: stop.", review_id=2, comment_id=20)],
        )
        self.assertEqual(status, "fail")

    def test_ignores_other_author_commit_and_earlier_run(self) -> None:
        reviews = [
            review("LGTM", login="someone"),
            review("LGTM", commit_id="other"),
            review("LGTM", submitted_at="2026-10-20T11:59:59Z"),
            review("LGTM", state="PENDING"),
            review("LGTM", state="DISMISSED"),
        ]
        status, _message = self.decide(reviews)
        self.assertEqual(status, "missing")

    def test_review_at_job_start_counts(self) -> None:
        status, _message = self.decide([review("LGTM", submitted_at=STARTED)])
        self.assertEqual(status, "pass")

    def test_job_name_matches_reusable_check_name(self) -> None:
        started = review_verdict.job_started_at(jobs("review / beefcake"), "beefcake")
        self.assertEqual(started, STARTED)

    def test_job_name_matches_plain_job_id(self) -> None:
        started = review_verdict.job_started_at(jobs("beefcake"), "beefcake")
        self.assertEqual(started, STARTED)

    def test_github_error_object_is_invalid(self) -> None:
        status, _message = review_verdict.verdict_from_files(
            json.dumps(jobs()),
            "beefcake",
            json.dumps({"message": "Not Found"}),
            HEAD,
            BOT,
        )
        self.assertEqual(status, "invalid")

    def test_missing_job_start_is_invalid(self) -> None:
        status, message = review_verdict.verdict_from_files(
            json.dumps({"jobs": [{"name": "other", "started_at": STARTED}]}),
            "beefcake",
            "[]",
            HEAD,
            BOT,
        )
        self.assertEqual(status, "invalid")
        self.assertIn("beefcake", message)

    def test_concatenated_review_pages(self) -> None:
        pages = json.dumps(
            [review("Still open.", submitted_at="2026-10-20T12:05:00Z", review_id=1)]
        ) + json.dumps([review("LGTM", submitted_at="2026-10-20T12:06:00Z", review_id=2)])
        status, _message = review_verdict.verdict_from_files(
            json.dumps(jobs()),
            "beefcake",
            pages,
            HEAD,
            BOT,
        )
        self.assertEqual(status, "pass")

    def test_cli_exit_codes(self) -> None:
        cases = [
            ([review("LGTM")], [], [], 0),
            ([review("Prior unresolved thread(s) still open.")], [], [], 0),
            (
                [review("")],
                [comment("Nit (optional): rename the local variable.")],
                [thread("Nit (optional): rename the local variable.")],
                0,
            ),
            (
                [review("")],
                [comment("Should fix: close the file.")],
                [],
                1,
            ),
            ([], [], [], 2),
        ]
        for reviews, comments, threads, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    jobs_path = root / "jobs.json"
                    reviews_path = root / "reviews.json"
                    comments_path = root / "comments.json"
                    threads_path = root / "threads.json"
                    jobs_path.write_text(json.dumps(jobs()), encoding="utf-8")
                    reviews_path.write_text(json.dumps(reviews), encoding="utf-8")
                    comments_path.write_text(json.dumps(comments), encoding="utf-8")
                    threads_path.write_text(json.dumps(threads), encoding="utf-8")
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "--jobs",
                            str(jobs_path),
                            "--job-name",
                            "beefcake",
                            "--reviews",
                            str(reviews_path),
                            "--comments",
                            str(comments_path),
                            "--threads",
                            str(threads_path),
                            "--head-sha",
                            HEAD,
                            "--bot",
                            BOT,
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, expected, completed.stdout)
                    self.assertTrue(completed.stdout.strip())


if __name__ == "__main__":
    unittest.main()
