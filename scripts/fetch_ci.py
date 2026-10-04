"""Cache commit statuses and Actions job results for the first bot-LGTM SHA.

Checks API and GraphQL CheckRun are 403 for this fine-grained token.
Required checks are read as follows:

- Every selected workflow run is expanded to job conclusions. A 30-SHA sample
  in data/raw/app/meta/ci_proxy_validation.json agreed with a workflow-level
  proxy on 23 SHAs and set use_workflow_proxy false, so the proxy is not used.
  Disagreements included a success proxy whose Playwright jobs were missing.
- A skipped job counts as a pass. GitHub reports a skipped required job as
  Success and does not block merge. Skipped docker-build or
  superadmin-storybook jobs are not coverage errors.
- Playwright jobs whose name ends in "(e2e-web)" or "(e2e-desktop)" count,
  including the uninterpolated template form.
- "Storybook / app screenshots" is a commit status, read from the Statuses API.

The first LGTM SHA comes from common.first_lgtm_sha, which includes bot issue
comments and review-thread comments. A comment LGTM uses the last commit at or
before that comment. Run selection prefers a success/failure conclusion over a
later cancelled run.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from common import (
    STATUS_CHECKS,
    bot_lgtm_events,
    contains_lgtm,
    current_study,
    fetch_prs_running,
    first_lgtm_sha,
    is_review_bot,
    parse_ts,
    pr_commits,
    required_check_contexts,
)
from ghutil import GitHub, GitHubError

S = current_study()
ROOT = S.root
PRS = S.prs
CI = S.ci

NEEDED = {
    ".github/workflows/ci.yml": [
        "lint",
        "docker-build",
        "tsc",
        "test (API)",
        "test (app)",
        "yarn (windows)",
        "build-foxglove-extension-pkg",
        "test-self-hosted-api",
        "build-foxglove-embed-pkg",
        "quick-checks",
        "generate-layout-api-python-classes",
        "build-self-hosted-app",
    ],
    ".github/workflows/playwright.yml": ["test (e2e-desktop)", "test (e2e-web)"],
    ".github/workflows/storybook.yml": ["superadmin-storybook"],
}


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, separators=(",", ":")))
    tmp.replace(path)


def load(path: Path):
    return json.loads(path.read_text())


def get_cached(gh: GitHub, path: Path, url: str):
    if path.exists():
        return load(path)
    payload, _headers = gh.request("GET", url)
    save(path, payload)
    return payload


def lgtm_sha_chain(pr: dict) -> list[str]:
    start = first_lgtm_sha(pr)
    if not start:
        return []
    events = bot_lgtm_events(pr)
    first_at = events[0]["at"] if events else None
    reviews = []
    for rev in (pr.get("reviews") or {}).get("nodes") or []:
        if not is_review_bot(rev.get("author")):
            continue
        submitted = rev.get("submittedAt")
        sha = (rev.get("commit") or {}).get("oid")
        if submitted:
            reviews.append({"at": submitted, "sha": sha, "body": rev.get("body") or ""})
    by_sha: dict[str, list] = {}
    for rev in reviews:
        if rev.get("sha"):
            by_sha.setdefault(rev["sha"], []).append(rev)
    stands = False
    seen = False
    started = False
    wanted = []
    for commit in pr_commits(pr):
        sha = commit["sha"]
        if sha in by_sha:
            last = max(by_sha[sha], key=lambda r: r["at"])
            stands = contains_lgtm(last["body"])
            seen = True
        if sha == start:
            started = True
            # A comment LGTM stands when this commit has no later bot review.
            # An earlier non-LGTM review must not clear it.
            here = by_sha.get(sha) or []
            if first_at is not None and (
                not here or max(parse_ts(r["at"]) for r in here) < first_at
            ):
                stands = True
                seen = True
        if started and seen and stands:
            wanted.append(sha)
        elif started and seen and not stands:
            break
    if not wanted:
        wanted = [start]
    out = []
    for sha in wanted:
        if sha not in out:
            out.append(sha)
    return out


def pick_runs(runs_payload: dict, only_paths: set[str] | None = None, *, all_paths: bool = False) -> dict[str, dict]:
    """One run per workflow path.

    The app call passes no filter and keeps NEEDED. all_paths reads every
    pull_request workflow. A success or failure conclusion beats a later
    cancelled run.
    """
    chosen: dict[str, dict] = {}
    if not all_paths and only_paths is None:
        only_paths = set(NEEDED)

    def rank(run: dict) -> tuple:
        good = 1 if run.get("conclusion") in ("success", "failure") else 0
        return (good, run.get("updated_at") or "")

    for run in runs_payload.get("workflow_runs") or []:
        path = run.get("path") or ""
        if run.get("event") != "pull_request":
            continue
        if only_paths is not None and path not in only_paths:
            continue
        prev = chosen.get(path)
        if prev is None or rank(run) > rank(prev):
            chosen[path] = run
    return chosen


def job_map(gh: GitHub, run: dict) -> dict[str, str]:
    run_id = run["id"]
    payload = get_cached(gh, CI / "jobs" / f"{run_id}.json", f"{S.api}/actions/runs/{run_id}/jobs?per_page=100")
    jobs = list(payload.get("jobs") or [])
    page = 2
    while payload.get("total_count", 0) > len(jobs) and page < 6:
        extra = get_cached(
            gh,
            CI / "jobs" / f"{run_id}_p{page}.json",
            f"{S.api}/actions/runs/{run_id}/jobs?per_page=100&page={page}",
        )
        jobs.extend(extra.get("jobs") or [])
        page += 1
    return {job.get("name"): job.get("conclusion") or job.get("status") for job in jobs if job.get("name")}


def match_job(jobs: dict[str, str], required: str) -> str:
    if required in jobs:
        return jobs[required]
    suffix = None
    if required.startswith("test (e2e-"):
        suffix = required[len("test ") :]  # "(e2e-web)" or "(e2e-desktop)"
    if suffix:
        for name, conclusion in jobs.items():
            if name.endswith(suffix):
                return conclusion
    return "missing"


def evaluate_sha(gh: GitHub, sha: str) -> dict:
    status = get_cached(gh, CI / "status" / f"{sha}.json", f"{S.api}/commits/{sha}/status")
    runs = get_cached(
        gh,
        CI / "runs" / f"{sha}.json",
        f"{S.api}/actions/runs?head_sha={sha}&per_page=100",
    )
    by_path = pick_runs(runs if isinstance(runs, dict) else {})
    statuses = {s.get("context"): (s.get("state") or "").lower() for s in (status.get("statuses") or [])}
    checks: dict[str, str] = {}
    source: dict[str, str] = {}
    for path, names in NEEDED.items():
        run = by_path.get(path)
        if run is None:
            for name in names:
                checks[name] = "missing"
                source[name] = "no_run"
        else:
            # A 5xx or timeout must not look like a failed required check.
            # main() leaves the PR unwritten so the next wave retries it.
            jobs = job_map(gh, run)
            for name in names:
                conclusion = match_job(jobs, name)
                if conclusion == "skipped":
                    checks[name] = "success"
                    source[name] = "skipped"
                else:
                    checks[name] = conclusion
                    source[name] = "job"
    for name in STATUS_CHECKS:
        checks[name] = statuses.get(name, "missing")
        source[name] = "commit_status"
    passed = all(v == "success" for v in checks.values())
    return {
        "sha": sha,
        "passed": passed,
        "failed": [k for k, v in checks.items() if v in ("failure", "timed_out", "cancelled", "startup_failure")],
        "missing": [k for k, v in checks.items() if v in ("missing", "skipped", "neutral", "action_required")],
        "checks": checks,
        "source": source,
        "workflow_conclusions": {path: (run.get("conclusion")) for path, run in by_path.items()},
        "status_state": status.get("state"),
    }


# Lower rank is a worse conclusion. A failing job hides a same-named success
# in another workflow. skipped is already turned into success by the caller.
_WORSE = {
    "failure": 0,
    "timed_out": 1,
    "startup_failure": 2,
    "cancelled": 3,
    "action_required": 4,
    "error": 5,
    "neutral": 6,
    "pending": 7,
    "queued": 8,
    "in_progress": 9,
    "missing": 10,
    "success": 11,
}


def _worse(a: str, b: str) -> str:
    return a if _WORSE.get(a, 6) <= _WORSE.get(b, 6) else b


def load_required_contexts() -> list[str]:
    path = S.meta / "required_checks.json"
    if path.exists():
        data = json.loads(path.read_text())
        return list(data.get("contexts") or [])
    rules_path = S.meta / "rulesets.json"
    rules = json.loads(rules_path.read_text()) if rules_path.exists() else []
    prot_path = S.meta / "protection.json"
    prot = json.loads(prot_path.read_text()) if prot_path.exists() else None
    return required_check_contexts(rules, prot)


def evaluate_sha_rules(gh: GitHub, sha: str, contexts: list[str]) -> dict:
    """Required checks from the repo ruleset or classic branch protection.

    A context matches a job name, then "workflow / job", then a commit status.
    The app path stays in evaluate_sha and is not used here.
    """
    status = get_cached(gh, CI / "status" / f"{sha}.json", f"{S.api}/commits/{sha}/status")
    runs = get_cached(
        gh,
        CI / "runs" / f"{sha}.json",
        f"{S.api}/actions/runs?head_sha={sha}&per_page=100",
    )
    if not contexts:
        return {
            "sha": sha,
            "passed": True,
            "failed": [],
            "missing": [],
            "checks": {},
            "source": {},
            "workflow_conclusions": {},
            "status_state": status.get("state"),
            "no_required_checks": True,
        }
    by_path = pick_runs(runs if isinstance(runs, dict) else {}, all_paths=True)
    statuses = {s.get("context"): (s.get("state") or "").lower() for s in (status.get("statuses") or [])}
    jobs: dict[str, str] = {}
    for path, run in by_path.items():
        named = job_map(gh, run)
        wf = run.get("name") or path
        for name, conclusion in named.items():
            raw = conclusion or "missing"
            if raw == "skipped":
                raw = "success"
            jobs[name] = _worse(jobs[name], raw) if name in jobs else raw
            qualified = f"{wf} / {name}"
            jobs[qualified] = _worse(jobs[qualified], raw) if qualified in jobs else raw
    checks: dict[str, str] = {}
    source: dict[str, str] = {}
    for name in contexts:
        if name in jobs:
            checks[name] = jobs[name]
            source[name] = "job"
            continue
        suffix = None
        if name.startswith("test (") and name.endswith(")"):
            suffix = name[len("test ") :]
        if suffix:
            matches = [c for job_name, c in jobs.items() if " / " not in job_name and job_name.endswith(suffix)]
            if len(set(matches)) == 1:
                checks[name] = matches[0]
                source[name] = "job_suffix"
                continue
        if name in statuses:
            state = statuses[name]
            checks[name] = "failure" if state == "error" else state
            source[name] = "commit_status"
            continue
        checks[name] = "missing"
        source[name] = "no_run"
    passed = all(v == "success" for v in checks.values())
    return {
        "sha": sha,
        "passed": passed,
        "failed": [k for k, v in checks.items() if v in ("failure", "timed_out", "cancelled", "startup_failure")],
        "missing": [k for k, v in checks.items() if v in ("missing", "skipped", "neutral", "action_required")],
        "checks": checks,
        "source": source,
        "workflow_conclusions": {path: (run.get("conclusion")) for path, run in by_path.items()},
        "status_state": status.get("state"),
    }


def pr_files() -> list[Path]:
    return [p for p in PRS.glob("*.json") if p.stem.isdigit()]


def main() -> None:
    gh = GitHub()
    idle = 0
    skipped: set[str] = set()
    contexts: list[str] | None = None
    if S.name != "app":
        while not (S.meta / "required_checks.json").exists() and not (S.meta / "rulesets.json").exists():
            if not fetch_prs_running():
                break
            time.sleep(5)
        contexts = load_required_contexts()
        print(f"required checks {len(contexts)}", flush=True)
    while True:
        wrote = 0
        for path in pr_files():
            out = CI / "eval" / f"{path.stem}.json"
            if out.exists():
                continue
            try:
                pr = json.loads(path.read_text())
            except json.JSONDecodeError:
                continue
            shas = lgtm_sha_chain(pr)
            if not shas:
                if bot_lgtm_events(pr):
                    save(out, {"number": int(path.stem), "shas": [], "evals": [], "sha_unknown": True})
                else:
                    save(out, {"number": int(path.stem), "shas": [], "evals": [], "no_lgtm": True})
                skipped.discard(path.stem)
                wrote += 1
                continue
            evals = []
            try:
                for sha in shas:
                    if contexts is None:
                        ev = evaluate_sha(gh, sha)
                    else:
                        ev = evaluate_sha_rules(gh, sha, contexts)
                    evals.append(ev)
                    if ev["passed"]:
                        break
            except GitHubError as exc:
                print(f"ci skip {path.stem}: {exc}", flush=True)
                if exc.status in (404, 422):
                    # Keep checks that already finished. A later SHA can 422
                    # after a force-push; the earlier failure still shows the
                    # LGTM SHA was not mergeable.
                    save(
                        out,
                        {
                            "number": int(path.stem),
                            "shas": shas,
                            "evals": evals,
                            "fetch_error": str(exc)[:300],
                        },
                    )
                    skipped.discard(path.stem)
                else:
                    skipped.add(path.stem)
                continue
            skipped.discard(path.stem)
            save(out, {"number": int(path.stem), "shas": shas, "evals": evals})
            wrote += 1
            if wrote % 40 == 0:
                print(f"ci wrote {wrote} this wave", flush=True)
        print(f"wave {wrote} evals {len(list((CI / 'eval').glob('*.json')))}", flush=True)
        if wrote == 0 and not fetch_prs_running():
            idle += 1
            if idle >= 2:
                print(f"ci fetch complete; {len(skipped)} PRs skipped", flush=True)
                return
        else:
            idle = 0
        time.sleep(10)


if __name__ == "__main__":
    main()
