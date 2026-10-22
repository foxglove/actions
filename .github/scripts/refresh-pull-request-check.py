#!/usr/bin/env python3
"""List failed pull_request review runs to re-run after an LGTM verdict.

GitHub shows the pull_request run of this workflow as its own check. A later
run on another event can pass without changing that check. Re-running the
failed pull_request run updates the check the pull request displays.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def workflow_path(workflow_ref: str) -> str:
    """Return the workflow file path from GITHUB_WORKFLOW_REF.

    The ref looks like ``owner/repo/.github/workflows/review.yml@refs/heads/main``.
    """
    path = workflow_ref.split("@", 1)[0]
    marker = ".github/workflows/"
    index = path.find(marker)
    if index < 0:
        return ""
    return path[index:]


def select_run_ids(
    payload: dict[str, Any],
    *,
    current_run_id: int,
    head_sha: str,
    workflow_file: str,
) -> list[int]:
    """Return failed pull_request runs of this workflow on this commit.

    The current run is excluded. A run that already had a second attempt is
    excluded so a failed refresh does not re-run itself forever.
    """
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        return []
    chosen: list[int] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        run_id = run.get("id")
        if not isinstance(run_id, int) or run_id == current_run_id:
            continue
        if run.get("event") != "pull_request":
            continue
        if run.get("conclusion") != "failure":
            continue
        if run.get("head_sha") != head_sha:
            continue
        if run.get("path") != workflow_file:
            continue
        attempt = run.get("run_attempt")
        if isinstance(attempt, int) and attempt >= 2:
            continue
        chosen.append(run_id)
    return chosen


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Print failed pull_request review run ids to re-run after LGTM."
    )
    parser.add_argument("--runs", required=True)
    parser.add_argument("--current-run", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--workflow-ref", required=True)
    args = parser.parse_args(argv)
    workflow_file = workflow_path(args.workflow_ref)
    if not workflow_file:
        print("Could not read the workflow path.", file=sys.stderr)
        return 1
    with open(args.runs, encoding="utf-8") as runs_file:
        payload = json.load(runs_file)
    if not isinstance(payload, dict):
        print("Could not read the workflow runs.", file=sys.stderr)
        return 1
    for run_id in select_run_ids(
        payload,
        current_run_id=args.current_run,
        head_sha=args.head_sha,
        workflow_file=workflow_file,
    ):
        print(run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
