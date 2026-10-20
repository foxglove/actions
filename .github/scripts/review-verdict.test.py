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


class ReviewVerdictTest(unittest.TestCase):
    def decide(self, reviews: list[dict], job_name: str = "beefcake"):
        payload = jobs(f"review / {job_name}")
        return review_verdict.verdict_from_files(
            json.dumps(payload),
            job_name,
            json.dumps(reviews),
            HEAD,
            BOT,
        )

    def test_lgtm_passes(self) -> None:
        status, message = self.decide([review("LGTM")])
        self.assertEqual(status, "lgtm")
        self.assertIn("LGTM", message)

    def test_lgtm_with_surrounding_whitespace_passes(self) -> None:
        status, _message = self.decide([review("\nLGTM\n")])
        self.assertEqual(status, "lgtm")

    def test_lgtm_with_hidden_marker_passes(self) -> None:
        status, _message = self.decide([review("LGTM\n\n<!-- beefcake-review -->")])
        self.assertEqual(status, "lgtm")

    def test_marker_only_fails(self) -> None:
        status, message = self.decide([review("<!-- beefcake-review -->")])
        self.assertEqual(status, "not-lgtm")
        self.assertIn("empty", message)

    def test_extra_text_with_marker_fails(self) -> None:
        status, _message = self.decide(
            [review("LGTM, with one note\n\n<!-- beefcake-review -->")]
        )
        self.assertEqual(status, "not-lgtm")

    def test_unresolved_threads_with_marker_fails(self) -> None:
        status, message = self.decide(
            [review("Prior unresolved thread(s) still open.\n\n<!-- beefcake-review -->")]
        )
        self.assertEqual(status, "not-lgtm")
        self.assertIn("Prior unresolved thread(s) still open.", message)

    def test_empty_body_fails(self) -> None:
        status, message = self.decide([review("")])
        self.assertEqual(status, "not-lgtm")
        self.assertIn("empty", message)

    def test_null_body_fails(self) -> None:
        status, _message = self.decide([review(None)])
        self.assertEqual(status, "not-lgtm")

    def test_unresolved_threads_body_fails(self) -> None:
        status, message = self.decide([review("Prior unresolved thread(s) still open.")])
        self.assertEqual(status, "not-lgtm")
        self.assertIn("Prior unresolved thread(s) still open.", message)

    def test_comment_body_fails(self) -> None:
        status, message = self.decide([review("Blocker: the migration drops the column.")])
        self.assertEqual(status, "not-lgtm")
        self.assertIn("migration drops the column", message)

    def test_lowercase_lgtm_fails(self) -> None:
        status, _message = self.decide([review("lgtm")])
        self.assertEqual(status, "not-lgtm")

    def test_lgtm_with_extra_text_fails(self) -> None:
        status, _message = self.decide([review("LGTM, with one note")])
        self.assertEqual(status, "not-lgtm")

    def test_latest_non_lgtm_wins(self) -> None:
        reviews = [
            review("LGTM", submitted_at="2026-10-20T12:05:00Z", review_id=1),
            review("Still open.", submitted_at="2026-10-20T12:06:00Z", review_id=2),
        ]
        status, _message = self.decide(reviews)
        self.assertEqual(status, "not-lgtm")

    def test_latest_lgtm_wins(self) -> None:
        reviews = [
            review("Still open.", submitted_at="2026-10-20T12:05:00Z", review_id=1),
            review("LGTM", submitted_at="2026-10-20T12:06:00Z", review_id=2),
        ]
        status, _message = self.decide(reviews)
        self.assertEqual(status, "lgtm")

    def test_same_timestamp_uses_higher_id(self) -> None:
        reviews = [
            review("LGTM", review_id=1),
            review("Still open.", review_id=2),
        ]
        status, _message = self.decide(reviews)
        self.assertEqual(status, "not-lgtm")

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
        self.assertEqual(status, "lgtm")

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
        self.assertEqual(status, "lgtm")

    def test_cli_exit_codes(self) -> None:
        cases = [
            ([review("LGTM")], 0),
            ([review("Prior unresolved thread(s) still open.")], 1),
            ([], 2),
        ]
        for reviews, expected in cases:
            with self.subTest(expected=expected):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    jobs_path = root / "jobs.json"
                    reviews_path = root / "reviews.json"
                    jobs_path.write_text(json.dumps(jobs()), encoding="utf-8")
                    reviews_path.write_text(json.dumps(reviews), encoding="utf-8")
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
                            "--head-sha",
                            HEAD,
                            "--bot",
                            BOT,
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(completed.returncode, expected)
                    self.assertTrue(completed.stdout.strip())


if __name__ == "__main__":
    unittest.main()
