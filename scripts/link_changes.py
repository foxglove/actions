"""Mark findings that were followed by a commit touching the same path."""

from __future__ import annotations

import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
REPO = Path("/tmp/foxglove-app")


def name_only(sha_a: str, sha_b: str) -> set[str]:
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = "/tmp/empty-gitconfig"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "/tmp/git-askpass.sh"
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(REPO),
            "-c",
            "credential.helper=",
            "-c",
            "credential.helper=!/tmp/git-cred.sh",
            "diff",
            "--name-only",
            sha_a,
            sha_b,
        ],
        text=True,
        capture_output=True,
        env=env,
    )
    if proc.returncode != 0:
        return set()
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def main() -> None:
    prs = {}
    with open(INTERIM / "prs.jsonl") as fh:
        for line in fh:
            pr = json.loads(line)
            prs[int(pr["number"])] = pr
    findings = []
    with open(INTERIM / "findings.jsonl") as fh:
        for line in fh:
            findings.append(json.loads(line))
    by_pr = defaultdict(list)
    for f in findings:
        by_pr[int(f["pr"])].append(f)
    cache: dict[tuple[str, str], set[str]] = {}
    for number, group in by_pr.items():
        pr = prs.get(number)
        if not pr:
            continue
        commits = pr.get("commits") or []
        head = pr.get("head_sha") or (commits[-1]["sha"] if commits else None)
        for finding in group:
            finding["code_change"] = False
            finding["code_change_confidence"] = "none"
            path = finding.get("path")
            at = finding.get("at")
            later = [c for c in commits if at and c.get("at") and c["at"] > at]
            if not later or not head:
                if finding.get("author_acknowledged"):
                    finding["code_change_confidence"] = "ack_only"
                continue
            base = None
            for c in commits:
                if c.get("at") and at and c["at"] <= at:
                    base = c["sha"]
            if base is None:
                base = commits[0]["sha"]
            if base == head:
                continue
            key = (base, head)
            if key not in cache:
                cache[key] = name_only(base, head)
            changed = cache[key]
            if path and path in changed:
                finding["code_change"] = True
                finding["code_change_confidence"] = "high" if finding.get("author_acknowledged") else "medium"
            elif not path and changed and finding.get("author_acknowledged"):
                finding["code_change"] = True
                finding["code_change_confidence"] = "low"
            elif finding.get("author_acknowledged"):
                finding["code_change_confidence"] = "ack_only"
    with open(INTERIM / "findings.jsonl", "w") as fh:
        for finding in findings:
            fh.write(json.dumps(finding, separators=(",", ":")) + "\n")
    changed = sum(1 for f in findings if f.get("code_change"))
    print(f"findings {len(findings)} with code change {changed} diffs {len(cache)}", flush=True)


if __name__ == "__main__":
    main()
