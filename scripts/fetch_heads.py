"""Fetch PR head commits for foxglove/app so blame and path diffs do not lazy-fetch.

The local clone is blob:none and only has main. Squash-merge SHAs are on main;
the pre-merge head and its ancestors are not, until refs/pull/N/head is fetched.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRS = ROOT / "data" / "raw" / "app" / "prs"
REPO = Path("/tmp/foxglove-app")
BATCH = 40


def git_env() -> dict:
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = "/tmp/empty-gitconfig"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "/tmp/git-askpass.sh"
    return env


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
            return
        mid = len(numbers) // 2
        fetch_batch(numbers[:mid])
        fetch_batch(numbers[mid:])


def fetch_running() -> bool:
    try:
        subprocess.check_output(["pgrep", "-f", "python3 scripts/fetch_prs.py"])
        return True
    except subprocess.CalledProcessError:
        return False


def pending() -> list[int]:
    out = []
    for path in PRS.glob("*.json"):
        if not path.stem.isdigit():
            continue
        number = int(path.stem)
        if not has_ref(number):
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
