#!/usr/bin/env python3
"""Tests for choosing which review check to re-run after LGTM."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("refresh-pull-request-check.py")
SPEC = importlib.util.spec_from_file_location("refresh_pull_request_check", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)

HEAD = "abc123"
PATH = ".github/workflows/review.yml"
REF = f"foxglove/promptjar/{PATH}@refs/heads/main"


def run(
    run_id: int,
    *,
    event: str = "pull_request",
    conclusion: str = "failure",
    head_sha: str = HEAD,
    path: str = PATH,
    attempt: int = 1,
) -> dict:
    return {
        "id": run_id,
        "event": event,
        "conclusion": conclusion,
        "head_sha": head_sha,
        "path": path,
        "run_attempt": attempt,
    }


class RefreshPullRequestCheckTest(unittest.TestCase):
    def test_workflow_path_from_ref(self) -> None:
        self.assertEqual(refresh.workflow_path(REF), PATH)

    def test_workflow_path_rejects_a_ref_without_the_marker(self) -> None:
        self.assertEqual(refresh.workflow_path("foxglove/promptjar@main"), "")

    def test_selects_the_failed_pull_request_run(self) -> None:
        payload = {
            "workflow_runs": [
                run(1),
                run(2, event="pull_request_review_comment"),
                run(3, conclusion="success"),
                run(4, head_sha="other"),
                run(5, path=".github/workflows/test.yml"),
                run(6, attempt=2),
                run(7),
            ]
        }
        self.assertEqual(
            refresh.select_run_ids(
                payload,
                current_run_id=7,
                head_sha=HEAD,
                workflow_file=PATH,
            ),
            [1],
        )

    def test_cli_prints_the_run_id(self) -> None:
        payload = {"workflow_runs": [run(41), run(42, conclusion="success")]}
        with tempfile.TemporaryDirectory() as directory:
            runs_path = Path(directory) / "runs.json"
            runs_path.write_text(json.dumps(payload), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--runs",
                    str(runs_path),
                    "--current-run",
                    "99",
                    "--head-sha",
                    HEAD,
                    "--workflow-ref",
                    REF,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "41")


if __name__ == "__main__":
    unittest.main()
