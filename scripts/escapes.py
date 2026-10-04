"""SZZ-style escape detection for foxglove/app.

Candidate fixes are merged PRs whose title indicates a fix, hotfix, regression, or
revert, or whose title/body references another pull request. For each removed line
in the fix, git blame on the parent commit identifies the introducing commit, and
the squash-commit subject supplies the introducing PR number.

Line presence at the introducer's first-bot-LGTM SHA vs its final head SHA separates
bucket B (present at the counterfactual SHA) from bucket D (added after it).
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common import FIX_TITLE_RE, PR_REF_RE, git_cred_helper, git_env, load_ci_index, parse_ts, study_repo

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
REPO = study_repo()
OUT = INTERIM / "escapes.jsonl"

PR_IN_SUBJECT = re.compile(r"\(#(\d{3,6})\)\s*$")
SKIP_PATH = re.compile(
    r"(^|/)(yarn\.lock|package-lock\.json|pnpm-lock\.yaml|.*\.snap|.*\.svg|CHANGELOG\.md)$"
)


def git(*args: str, check: bool = True) -> str:
    env = git_env()
    cmd = [
        "git",
        "-C",
        str(REPO),
        "-c",
        "credential.helper=",
        "-c",
        f"credential.helper=!{git_cred_helper()}",
        "-c",
        "safe.directory=*",
        *args,
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, env=env)
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr[-400:] or f"git {' '.join(args[:4])} failed")
    return proc.stdout


def parse_removed_lines(diff_text: str, cap: int = 80) -> list[dict]:
    """Return up to `cap` removed lines with file path and 1-based old line number."""
    removed = []
    path = None
    old_line = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            path = None
            old_line = None
            continue
        if line.startswith("--- "):
            old = line[4:]
            if old.startswith("a/"):
                path = old[2:]
            elif old == "/dev/null":
                path = None
            else:
                path = old
            continue
        if line.startswith("@@"):
            m = re.search(r"@@ -(\d+)(?:,(\d+))? \+", line)
            if not m:
                old_line = None
                continue
            old_line = int(m.group(1))
            continue
        if path is None or old_line is None:
            continue
        if line.startswith("-") and not line.startswith("---"):
            text = line[1:]
            if path and not SKIP_PATH.search(path) and text.strip():
                removed.append({"path": path, "line": old_line, "text": text})
                if len(removed) >= cap:
                    return removed
            old_line += 1
        elif line.startswith("+") and not line.startswith("+++"):
            continue
        elif line.startswith("\\"):
            continue
        else:
            # context line
            old_line += 1
    return removed


def blame_lines(parent: str, path: str, lines: list[int]) -> dict[int, str]:
    if not lines:
        return {}
    start, end = min(lines), max(lines)
    # One blame for the span, then keep only requested lines.
    try:
        out = git(
            "blame",
            "--line-porcelain",
            "-L",
            f"{start},{end}",
            parent,
            "--",
            path,
            check=True,
        )
    except RuntimeError:
        return {}
    mapping = {}
    current_sha = None
    current_line = None
    for raw in out.splitlines():
        if re.match(r"^[0-9a-f]{40} ", raw):
            current_sha = raw.split()[0]
            # second field is the original line, third is the final line number
            parts = raw.split()
            if len(parts) >= 3 and parts[2].isdigit():
                current_line = int(parts[2])
            continue
        if raw.startswith("\t") and current_sha and current_line:
            if current_line in lines:
                mapping[current_line] = current_sha
            current_sha = None
    return {ln: mapping[ln] for ln in lines if ln in mapping}


def subject_pr(sha: str, cache: dict[str, int | None]) -> int | None:
    if sha in cache:
        return cache[sha]
    try:
        subject = git("log", "-1", "--format=%s", sha, check=True).strip()
    except RuntimeError:
        cache[sha] = None
        return None
    m = PR_IN_SUBJECT.search(subject)
    cache[sha] = int(m.group(1)) if m else None
    return cache[sha]


def file_text(sha: str | None, path: str, cache: dict) -> str | None:
    key = (sha, path)
    if key in cache:
        return cache[key]
    if not sha:
        cache[key] = None
        return None
    env = git_env()
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(REPO),
            "-c",
            "credential.helper=",
            "-c",
            f"credential.helper=!{git_cred_helper()}",
            "show",
            f"{sha}:{path}",
        ],
        text=True,
        capture_output=True,
        env=env,
    )
    cache[key] = proc.stdout if proc.returncode == 0 else None
    return cache[key]


def line_present(text: str | None, line: str) -> str:
    if text is None or not line.strip():
        return "absent_file" if text is None else "blank"
    count = text.splitlines().count(line)
    if count == 1:
        return "unique"
    if count > 1:
        return "duplicate"
    return "absent"


def load_counterfactual() -> dict[int, dict]:
    """First green SHA at or after the first bot LGTM, while LGTM still stands."""
    return load_ci_index(ROOT / "data" / "raw" / "app" / "ci" / "eval")


def candidate(pr: dict) -> bool:
    if not pr.get("merged"):
        return False
    title = pr.get("title") or ""
    body = pr.get("body") or ""
    if FIX_TITLE_RE.search(title):
        return True
    # A body that says "fixes" is not enough: GitHub closing syntax ("Fixes FG-123")
    # appears on ordinary PRs. Require a reference to another pull request.
    refs = {int(n) for n in PR_REF_RE.findall(title + "\n" + body)}
    refs.discard(int(pr["number"]))
    if refs and FIX_TITLE_RE.search(title + "\n" + body):
        return True
    return False


def main() -> None:
    prs = []
    with open(INTERIM / "prs.jsonl") as fh:
        for line in fh:
            prs.append(json.loads(line))
    by_number = {int(p["number"]): p for p in prs}
    ci_cf = load_counterfactual()
    for pr in prs:
        info = ci_cf.get(int(pr["number"]))
        if info:
            pr["counterfactual_sha"] = info["sha"]
            pr["mergeable_at_lgtm"] = info["mergeable_at_lgtm"]
    fixes = [p for p in prs if candidate(p) and p.get("merge_commit")]
    print(f"candidate fix PRs {len(fixes)}", flush=True)
    subject_cache: dict[str, int | None] = {}
    blob_cache: dict = {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with OUT.open("w") as out:
        for i, fix in enumerate(fixes):
            merge = fix["merge_commit"]
            try:
                parent = git("rev-parse", f"{merge}^", check=True).strip()
            except RuntimeError:
                continue
            try:
                diff = git("diff", "-U0", parent, merge, check=True)
            except RuntimeError:
                continue
            removed = parse_removed_lines(diff)
            if not removed:
                continue
            by_file: dict[str, list] = defaultdict(list)
            for item in removed:
                by_file[item["path"]].append(item)
            attributions = []
            for path, items in by_file.items():
                wanted = [it["line"] for it in items]
                blamed = blame_lines(parent, path, wanted)
                for it in items:
                    sha = blamed.get(it["line"])
                    if not sha:
                        continue
                    intro = subject_pr(sha, subject_cache)
                    attributions.append({**it, "blame_sha": sha, "intro_pr": intro})
            if not attributions:
                continue
            counts: dict[int, int] = defaultdict(int)
            for a in attributions:
                if a["intro_pr"]:
                    counts[a["intro_pr"]] += 1
            if not counts:
                continue
            for intro_pr, n_lines in counts.items():
                intro = by_number.get(intro_pr)
                if not intro:
                    continue
                share = n_lines / max(1, len(attributions))
                conf = "high" if share >= 0.7 else "medium" if share >= 0.4 else "low"
                cf = intro.get("counterfactual_sha") or intro.get("first_lgtm_sha")
                head = intro.get("head_sha")
                lines_for = [a for a in attributions if a["intro_pr"] == intro_pr]
                presence = []
                for a in lines_for[:12]:
                    cf_text = file_text(cf, a["path"], blob_cache) if cf else None
                    head_text = file_text(head, a["path"], blob_cache) if head else None
                    presence.append(
                        {
                            "path": a["path"],
                            "line_text": a["text"][:240],
                            "at_counterfactual": line_present(cf_text, a["text"]) if cf else "no_sha",
                            "at_head": line_present(head_text, a["text"]) if head else "no_sha",
                        }
                    )
                fix_merged = parse_ts(fix.get("merged_at"))
                intro_merged = parse_ts(intro.get("merged_at"))
                delta_days = None
                if fix_merged and intro_merged:
                    delta_days = (fix_merged - intro_merged).total_seconds() / 86400.0
                within_30 = None
                if delta_days is not None:
                    within_30 = 0 <= delta_days <= 30
                # Partial follow-up: introducer merged after 2026-09-03 has <30 days by 2026-10-03.
                partial_window = bool(intro_merged and intro_merged >= datetime(2026, 9, 3, tzinfo=timezone.utc))
                out.write(
                    json.dumps(
                        {
                            "fix_pr": fix["number"],
                            "fix_url": fix.get("url"),
                            "fix_title": fix.get("title"),
                            "fix_merged_at": fix.get("merged_at"),
                            "intro_pr": intro_pr,
                            "intro_url": intro.get("url"),
                            "intro_merged_at": intro.get("merged_at"),
                            "intro_month": intro.get("month"),
                            "intro_in_cohort": intro.get("in_cohort"),
                            "intro_bot_lgtm": intro.get("bot_lgtm"),
                            "intro_merged": intro.get("merged"),
                            "intro_author_type": intro.get("author_type"),
                            "lines": n_lines,
                            "share": round(share, 3),
                            "confidence": conf,
                            "delta_days": delta_days,
                            "within_30_days": within_30,
                            "partial_followup_window": partial_window,
                            "presence": presence,
                        },
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                written += 1
            if (i + 1) % 25 == 0:
                print(f"fixes scanned {i+1}/{len(fixes)} links {written}", flush=True)
    print(f"wrote {written} introducer links", flush=True)


if __name__ == "__main__":
    main()
