"""Fetch PR head commits for foxglove/app so blame and path diffs do not lazy-fetch.

The local clone is blob:none and only has main. Squash-merge SHAs are on main;
the pre-merge head and its ancestors are not, until refs/pull/N/head is fetched.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from common import git_env, study_repo

ROOT = Path(__file__).resolve().parents[1]
PRS = ROOT / "data" / "raw" / "app" / "prs"
FAILED = ROOT / "data" / "raw" / "app" / "meta" / "head_fetch_failed.json"
REPO = study_repo()
BATCH = 40


def has_ref(number: int) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(REPO), "show-ref", "--verify", "--quiet", f"refs/study/{number}"],
        env=git_env(),
    )
    return proc.returncode == 0


def fetch_batch(numbers: list[int]) -> None:
    refspecs = [f"pull/{n}/head:refs/study/{n}" for n in numbers]
    cmd = [
        "git",
        "-C",
        str(REPO),
        "-c",
        "credential.helper=",
        "-c",
        "credential.helper=!/tmp/git-cred.sh",
        "fetch",
        "--filter=blob:none",
        "--no-tags",
        "origin",
        *refspecs,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, env=git_env())
    if proc.returncode != 0:
        # Fall back one by one so one deleted PR does not drop the batch.
        print(f"batch failed ({proc.returncode}); splitting {numbers[0]}..{numbers[-1]}", flush=True)
        print(proc.stderr[-300:].replace("\n", " "), flush=True)
        if len(numbers) == 1:
            record_failure(numbers[0])
            return
        mid = len(numbers) // 2
        fetch_batch(numbers[:mid])
        fetch_batch(numbers[mid:])


def fetch_running() -> bool:
    # The tmux supervisor's argv also contains this script name, so a plain
    # pgrep -f match stays true after the Python process exits.
    try:
        out = subprocess.check_output(["pgrep", "-af", "scripts/fetch_prs.py"], text=True)
    except subprocess.CalledProcessError:
        return False
    return any(
        "python3" in line and "scripts/fetch_prs.py" in line and "tmux" not in line
        for line in out.splitlines()
    )


def load_failures() -> set[int]:
    if not FAILED.exists():
        return set()
    try:
        return {int(n) for n in json.loads(FAILED.read_text())}
    except (json.JSONDecodeError, TypeError, ValueError):
        return set()


def record_failure(number: int) -> None:
    failed = load_failures()
    failed.add(number)
    FAILED.parent.mkdir(parents=True, exist_ok=True)
    FAILED.write_text(json.dumps(sorted(failed)))
    print(f"head fetch failed for {number}", flush=True)


def pending() -> list[int]:
    failed = load_failures()
    out = []
    for path in PRS.glob("*.json"):
        if not path.stem.isdigit():
            continue
        number = int(path.stem)
        if number in failed or has_ref(number):
            continue
        out.append(number)
    return out


def main() -> None:
    idle = 0
    while True:
        missing = pending()
        print(f"heads missing {len(missing)}", flush=True)
        if not missing:
            if fetch_running():
                time.sleep(20)
                continue
            idle += 1
            if idle >= 2:
                print("head fetch complete", flush=True)
                return
            time.sleep(15)
            continue
        idle = 0
        # Newest first: the pilot's September findings need these sooner.
        missing.sort(reverse=True)
        batch = missing[:BATCH]
        fetch_batch(batch)
        print(f"fetched up to {len(batch)} ending near {batch[-1]}", flush=True)


if __name__ == "__main__":
    main()
