"""Mark findings that were followed by a commit touching the same path."""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path

from common import git_cred_helper, git_env, study_repo

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
REPO = study_repo()


def name_only(sha_a: str, sha_b: str) -> set[str] | None:
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(REPO),
            "-c",
            "credential.helper=",
            "-c",
            f"credential.helper=!{git_cred_helper()}",
            "diff",
            "--name-only",
            sha_a,
            sha_b,
        ],
        text=True,
        capture_output=True,
        env=git_env(),
    )
    if proc.returncode != 0:
        return None
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
    cache: dict[tuple[str, str], set[str] | None] = {}
    diff_failures = 0
    rebased = 0
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
                # A rebase rewrites committedDate. The commit before the
                # finding is not known, so a same-path change cannot be shown.
                finding["code_change_confidence"] = "rebased_unknown"
                rebased += 1
                continue
            if base == head:
                continue
            key = (base, head)
            if key not in cache:
                cache[key] = name_only(base, head)
            changed = cache[key]
            if changed is None:
                finding["code_change_confidence"] = "diff_failed"
                diff_failures += 1
                continue
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
    print(
        f"findings {len(findings)} with code change {changed} diffs {len(cache)} diff_failed {diff_failures} rebased {rebased}",
        flush=True,
    )


if __name__ == "__main__":
    main()
