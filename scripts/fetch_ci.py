"""Cache commit statuses and Actions runs for the first bot-LGTM SHA.

Checks API and GraphQL CheckRun are 403 for this fine-grained token.
Required checks are inferred as follows:

- A workflow run whose conclusion is success is treated as its required jobs
  passing. On a 38-run sample, a successful CI workflow disagreed with a
  required job once (docker-build skipped). Storybook success disagreed for
  superadmin-storybook on 3/35 runs (job skipped). Those rates are reported
  as a coverage gap; they are not re-fetched for every SHA.
- If the selected run's conclusion is not success, job conclusions are fetched
  and matched by name. Playwright jobs whose name ends in "(e2e-web)" or
  "(e2e-desktop)" count, including the uninterpolated template form.
- "Storybook / app screenshots" is a commit status, read from the Statuses API.
  Missing or failing status means the SHA was not mergeable under the current
  ruleset.

Run selection prefers a success/failure conclusion over a later cancelled run.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from common import JOB_CHECKS, STATUS_CHECKS, WORKFLOW_FOR_JOB, contains_lgtm, is_review_bot
from ghutil import GitHub, GitHubError

ROOT = Path(__file__).resolve().parents[1]
PRS = ROOT / "data" / "raw" / "app" / "prs"
CI = ROOT / "data" / "raw" / "app" / "ci"

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
    reviews = []
    for rev in (pr.get("reviews") or {}).get("nodes") or []:
        if not is_review_bot(rev.get("author")):
            continue
        submitted = rev.get("submittedAt")
        sha = (rev.get("commit") or {}).get("oid")
        if submitted:
            reviews.append({"at": submitted, "sha": sha, "body": rev.get("body") or ""})
    reviews.sort(key=lambda r: r["at"])
    lgtm = [r for r in reviews if contains_lgtm(r["body"]) and r.get("sha")]
    if not lgtm:
        return []
    commits = []
    for c in (pr.get("commits") or {}).get("nodes") or []:
        commit = c.get("commit") or {}
        if commit.get("oid") and (commit.get("committedDate") or commit.get("authoredDate")):
            commits.append((commit.get("committedDate") or commit.get("authoredDate"), commit["oid"]))
    commits.sort()
    by_sha: dict[str, list] = {}
    for rev in reviews:
        if rev.get("sha"):
            by_sha.setdefault(rev["sha"], []).append(rev)
    stands = False
    seen = False
    started = False
    wanted = []
    for _at, sha in commits:
        if sha in by_sha:
            last = max(by_sha[sha], key=lambda r: r["at"])
            stands = contains_lgtm(last["body"])
            seen = True
        if sha == lgtm[0]["sha"]:
            started = True
        if started and seen and stands:
            wanted.append(sha)
        elif started and seen and not stands:
            break
    if not wanted:
        wanted = [lgtm[0]["sha"]]
    out = []
    for sha in wanted:
        if sha not in out:
            out.append(sha)
    return out


def pick_runs(runs_payload: dict) -> dict[str, dict]:
    chosen: dict[str, dict] = {}

    def rank(run: dict) -> tuple:
        good = 1 if run.get("conclusion") in ("success", "failure") else 0
        return (good, run.get("updated_at") or "")

    for run in runs_payload.get("workflow_runs") or []:
        path = run.get("path") or ""
        if path not in NEEDED or run.get("event") != "pull_request":
            continue
        prev = chosen.get(path)
        if prev is None or rank(run) > rank(prev):
            chosen[path] = run
    return chosen


def job_map(gh: GitHub, run: dict) -> dict[str, str]:
    run_id = run["id"]
    payload = get_cached(gh, CI / "jobs" / f"{run_id}.json", f"/repos/foxglove/app/actions/runs/{run_id}/jobs?per_page=100")
    jobs = list(payload.get("jobs") or [])
    page = 2
    while payload.get("total_count", 0) > len(jobs) and page < 6:
        extra = get_cached(
            gh,
            CI / "jobs" / f"{run_id}_p{page}.json",
            f"/repos/foxglove/app/actions/runs/{run_id}/jobs?per_page=100&page={page}",
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
    status = get_cached(gh, CI / "status" / f"{sha}.json", f"/repos/foxglove/app/commits/{sha}/status")
    runs = get_cached(
        gh,
        CI / "runs" / f"{sha}.json",
        f"/repos/foxglove/app/actions/runs?head_sha={sha}&per_page=100",
    )
    by_path = pick_runs(runs if isinstance(runs, dict) else {})
    statuses = {s.get("context"): (s.get("state") or "").lower() for s in (status.get("statuses") or [])}
    checks: dict[str, str] = {}
    source: dict[str, str] = {}
    for path, names in NEEDED.items():
        run = by_path.get(path)
        conclusion = (run or {}).get("conclusion") or "missing"
        if conclusion == "success":
            for name in names:
                checks[name] = "success"
                source[name] = "workflow_success"
        elif run is None:
            for name in names:
                checks[name] = "missing"
                source[name] = "no_run"
        else:
            try:
                jobs = job_map(gh, run)
            except GitHubError as exc:
                jobs = {}
                source["_error"] = str(exc)[:180]
            for name in names:
                checks[name] = match_job(jobs, name)
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


def pr_files() -> list[Path]:
    return [p for p in PRS.glob("*.json") if p.stem.isdigit()]


def fetch_running() -> bool:
    try:
        subprocess.check_output(["pgrep", "-f", "python3 scripts/fetch_prs.py"])
        return True
    except subprocess.CalledProcessError:
        return False


def main() -> None:
    gh = GitHub()
    idle = 0
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
                save(out, {"number": int(path.stem), "shas": [], "evals": [], "no_lgtm": True})
                wrote += 1
                continue
            evals = []
            for sha in shas:
                ev = evaluate_sha(gh, sha)
                evals.append(ev)
                if ev["passed"]:
                    break
            save(out, {"number": int(path.stem), "shas": shas, "evals": evals})
            wrote += 1
            if wrote % 40 == 0:
                print(f"ci wrote {wrote} this wave", flush=True)
        print(f"wave {wrote} evals {len(list((CI / 'eval').glob('*.json')))}", flush=True)
        if wrote == 0 and not fetch_running():
            idle += 1
            if idle >= 2:
                print("ci fetch complete", flush=True)
                return
        else:
            idle = 0
        time.sleep(10)


if __name__ == "__main__":
    main()
