"""Turn cached PR payloads into interim JSONL tables.

Does not classify findings. findings.jsonl includes a before/after timing field for
the metrics step. Classifier batches are a separate file and contain only id,
comment, path, diff_hunk, and replies. They do not include timing.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from common import (
    ACK_RE,
    WINDOW_END,
    WINDOW_START,
    bot_lgtm_events,
    contains_lgtm,
    hours_between,
    is_bot_author,
    is_review_bot,
    iso,
    month_key,
    norm_login,
    first_lgtm_sha,
    parse_ts,
    size_bucket,
    tenure_bucket,
    current_study,
)

S = current_study()
ROOT = S.root
PRS_DIR = S.prs
META = S.meta
INTERIM = S.interim
GIT_LOG = S.clone

NOREPLY_RE = re.compile(r"^(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com$", re.I)
SHORT_ACK_RE = re.compile(
    r"^(lgtm|looks good|looks good to me|thanks!?|thank you!?|approved|nice|ship it)[.! ]*$",
    re.I,
)


def load_members() -> set[str]:
    members = json.loads((META / "members.json").read_text())
    return {m["login"] for m in members}


def git_first_commits() -> dict[str, datetime]:
    """Earliest commit timestamp per GitHub login, from noreply emails and raw emails."""
    import subprocess

    env_cmd = [
        "git",
        "-C",
        str(GIT_LOG),
        "-c",
        "safe.directory=*",
        "log",
        "--format=%aI%x09%aE",
    ]
    # Bypass the global URL rewrite; this is a local read.
    out = subprocess.check_output(env_cmd, text=True, errors="replace")
    first_email: dict[str, datetime] = {}
    first_login: dict[str, datetime] = {}
    for line in out.splitlines():
        if "\t" not in line:
            continue
        ts_s, email = line.split("\t", 1)
        email = email.strip().lower()
        try:
            ts = datetime.fromisoformat(ts_s)
        except ValueError:
            continue
        if email not in first_email or ts < first_email[email]:
            first_email[email] = ts
        m = NOREPLY_RE.match(email)
        if m:
            login = m.group(1)
            if login not in first_login or ts < first_login[login]:
                first_login[login] = ts
    # Stash email map for login linking via PR commit authors.
    (INTERIM).mkdir(parents=True, exist_ok=True)
    return first_login, first_email


def nodes(pr: dict, field: str) -> list:
    return ((pr.get(field) or {}).get("nodes") or [])


def author_login(author: dict | None) -> str | None:
    if not author:
        return None
    return author.get("login")


def collect_lgtm_events(pr: dict) -> list[dict]:
    return bot_lgtm_events(pr)


def bot_reviews(pr: dict) -> list[dict]:
    rows = []
    for rev in nodes(pr, "reviews"):
        if not is_review_bot(rev.get("author")):
            continue
        rows.append(
            {
                "at": parse_ts(rev.get("submittedAt")),
                "sha": (rev.get("commit") or {}).get("oid"),
                "state": rev.get("state"),
                "body": rev.get("body") or "",
                "database_id": rev.get("databaseId"),
            }
        )
    rows = [r for r in rows if r["at"] is not None]
    rows.sort(key=lambda r: r["at"])
    return rows


def lgtm_stands_by_sha(commits: list[dict], reviews: list[dict]) -> dict[str, bool]:
    """Latest bot review whose commit is this SHA, else the previous applicable review.

    Stale reviews are not dismissed (ruleset dismiss_stale_reviews_on_push = false),
    so an LGTM stands on later commits until a newer bot review lands on a later SHA.
    """
    by_sha: dict[str, list] = defaultdict(list)
    for rev in reviews:
        if rev.get("sha"):
            by_sha[rev["sha"]].append(rev)
    state_is_lgtm = False
    seen = False
    out = {}
    for commit in commits:
        sha = commit["sha"]
        if sha in by_sha:
            last = max(by_sha[sha], key=lambda r: r["at"])
            state_is_lgtm = contains_lgtm(last["body"])
            seen = True
        out[sha] = bool(seen and state_is_lgtm)
    return out


def top_dirs(files: list[dict]) -> list[str]:
    dirs = set()
    for f in files:
        path = f.get("path") or ""
        if not path:
            continue
        dirs.add(path.split("/", 1)[0] if "/" in path else "(root)")
    return sorted(dirs)


def human_threads(pr: dict) -> list[dict]:
    findings = []
    for thread in nodes(pr, "reviewThreads"):
        comments = (thread.get("comments") or {}).get("nodes") or []
        if not comments:
            continue
        first = comments[0]
        if is_bot_author(first.get("author")) or is_review_bot(first.get("author")):
            continue
        if not author_login(first.get("author")):
            continue
        replies = []
        for c in comments[1:]:
            replies.append(
                {
                    "login": author_login(c.get("author")),
                    "bot": is_bot_author(c.get("author")),
                    "at": c.get("createdAt"),
                    "body": c.get("body") or "",
                }
            )
        findings.append(
            {
                "source": "review_thread",
                "finding_id": f"thread-{thread.get('id')}",
                "at": parse_ts(first.get("createdAt")),
                "login": author_login(first.get("author")),
                "body": first.get("body") or "",
                "path": first.get("path") or thread.get("path"),
                "line": first.get("line") or thread.get("line"),
                "diff_hunk": first.get("diffHunk") or "",
                "replies": replies,
                "thread_resolved": bool(thread.get("isResolved")),
                "database_id": first.get("databaseId"),
            }
        )
    return findings


def human_review_bodies(pr: dict) -> list[dict]:
    rows = []
    for rev in nodes(pr, "reviews"):
        author = rev.get("author")
        if is_bot_author(author) or is_review_bot(author):
            continue
        body = (rev.get("body") or "").strip()
        state = rev.get("state") or ""
        if not body:
            continue
        if state not in ("CHANGES_REQUESTED", "COMMENTED", "APPROVED"):
            continue
        if state == "APPROVED" and (SHORT_ACK_RE.match(body) or contains_lgtm(body) and len(body) < 40):
            continue
        if state == "COMMENTED" and SHORT_ACK_RE.match(body):
            continue
        rows.append(
            {
                "source": "changes_requested" if state == "CHANGES_REQUESTED" else "review_body",
                "finding_id": f"review-{rev.get('databaseId')}",
                "at": parse_ts(rev.get("submittedAt")),
                "login": author_login(author),
                "body": body,
                "path": None,
                "line": None,
                "diff_hunk": "",
                "replies": [],
                "thread_resolved": None,
                "database_id": rev.get("databaseId"),
                "review_state": state,
            }
        )
    return rows


def link_change(finding: dict, commits: list[dict], author: str | None) -> dict:
    """Link a later commit that touches the same path. Timing-only links are low confidence."""
    at = finding["at"]
    path = finding.get("path")
    later = [c for c in commits if at and c["at"] and c["at"] > at]
    # Without per-commit file lists, a same-path link is resolved in a second pass
    # when git is available. Here we only record candidate SHAs.
    reply_text = "\n".join(r["body"] for r in finding.get("replies") or [])
    author_replies = [r for r in finding.get("replies") or [] if r.get("login") == author and not r.get("bot")]
    author_text = "\n".join(r["body"] for r in author_replies)
    acked = bool(ACK_RE.search(author_text))
    return {
        "later_commit_shas": [c["sha"] for c in later],
        "author_acknowledged": acked,
        "any_reply": bool(reply_text.strip()),
    }


def closed_info(pr: dict) -> dict:
    actor = None
    closed_at = parse_ts(pr.get("closedAt"))
    for item in nodes(pr, "timelineItems"):
        if item.get("__typename") == "ClosedEvent":
            actor = author_login(item.get("actor"))
    reason = None
    if pr.get("mergedAt"):
        return {"closed_by": actor, "closing_comment": None}
    comments = []
    for c in nodes(pr, "comments"):
        at = parse_ts(c.get("createdAt"))
        if closed_at and at and at <= closed_at:
            comments.append((at, author_login(c.get("author")), c.get("body") or ""))
    comments = [c for c in comments if c[0] is not None]
    comments.sort(key=lambda x: x[0])
    # Prefer a comment by the closer in the 3 days before close; else the last comment.
    if closed_at and comments:
        window = [
            c
            for c in comments
            if c[0] <= closed_at and (closed_at - c[0]).total_seconds() <= 3 * 86400 and (actor is None or c[1] == actor)
        ]
        chosen = window[-1] if window else comments[-1]
        reason = chosen[2][:2000]
    return {"closed_by": actor, "closing_comment": reason}


def review_request_times(pr: dict) -> list[datetime]:
    times = []
    for item in nodes(pr, "timelineItems"):
        if item.get("__typename") == "ReviewRequestedEvent":
            at = parse_ts(item.get("createdAt"))
            if at:
                times.append(at)
    return sorted(times)


def human_approvals(pr: dict) -> list[dict]:
    rows = []
    for rev in nodes(pr, "reviews"):
        if rev.get("state") != "APPROVED":
            continue
        if is_bot_author(rev.get("author")) or is_review_bot(rev.get("author")):
            continue
        at = parse_ts(rev.get("submittedAt"))
        if not at:
            continue
        rows.append(
            {
                "at": at,
                "login": author_login(rev.get("author")),
                "body": rev.get("body") or "",
                "sha": (rev.get("commit") or {}).get("oid"),
                "database_id": rev.get("databaseId"),
            }
        )
    rows.sort(key=lambda r: r["at"])
    return rows


def human_activity_before(pr: dict, cutoff: datetime | None) -> bool:
    if cutoff is None:
        return False
    for rev in nodes(pr, "reviews"):
        if is_bot_author(rev.get("author")) or is_review_bot(rev.get("author")):
            continue
        at = parse_ts(rev.get("submittedAt"))
        if at and at < cutoff:
            return True
    for thread in nodes(pr, "reviewThreads"):
        comments = (thread.get("comments") or {}).get("nodes") or []
        if not comments:
            continue
        first = comments[0]
        if is_bot_author(first.get("author")) or is_review_bot(first.get("author")):
            continue
        at = parse_ts(first.get("createdAt"))
        if at and at < cutoff:
            return True
    return False


def dismissal_count(pr: dict) -> int:
    return sum(1 for item in nodes(pr, "timelineItems") if item.get("__typename") == "ReviewDismissedEvent")


def force_push_count(pr: dict) -> int:
    return sum(1 for item in nodes(pr, "timelineItems") if item.get("__typename") == "HeadRefForcePushedEvent")


def build_email_login_map(pr_paths: list[Path]) -> dict[str, str]:
    """email -> login from commit author objects when the API provided them.

    The slim query stores commit authors only when present. Many payloads only
    have messageHeadline. Noreply mapping covers the rest.
    """
    mapping = {}
    for path in pr_paths:
        pr = json.loads(path.read_text())
        for c in nodes(pr, "commits"):
            commit = c.get("commit") or {}
            for person in ((commit.get("authors") or {}).get("nodes") or []):
                email = (person.get("email") or "").lower()
                user = person.get("user") or {}
                login = user.get("login")
                if email and login:
                    mapping[email] = login
    return mapping


def main() -> None:
    INTERIM.mkdir(parents=True, exist_ok=True)
    members = load_members()
    print("loading git history for tenure", flush=True)
    first_login, first_email = git_first_commits()
    paths = sorted((p for p in PRS_DIR.glob("*.json") if p.stem.isdigit()), key=lambda p: int(p.stem))
    print(f"parsing {len(paths)} pr files", flush=True)
    email_logins = build_email_login_map(paths)
    # Fold email first-seen into logins.
    for email, ts in first_email.items():
        login = email_logins.get(email)
        if not login:
            m = NOREPLY_RE.match(email)
            login = m.group(1) if m else None
        if not login:
            continue
        if login not in first_login or ts < first_login[login]:
            first_login[login] = ts

    pr_out = open(INTERIM / "prs.jsonl", "w")
    finding_out = open(INTERIM / "findings.jsonl", "w")
    example_lgtm = []
    bot_round_counts = []
    n = 0
    truncated_n = 0
    for path in paths:
        try:
            pr = json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"skip partial {path.name}", flush=True)
            continue
        n += 1
        if pr.get("_truncated_fields"):
            truncated_n += 1
        created = parse_ts(pr.get("createdAt"))
        merged = parse_ts(pr.get("mergedAt"))
        closed = parse_ts(pr.get("closedAt"))
        author = pr.get("author") or {}
        login = author_login(author) or "ghost"
        author_type = "bot" if is_bot_author(author) else "human"
        in_cohort = bool(created and WINDOW_START <= created < WINDOW_END)
        additions = pr.get("additions") or 0
        deletions = pr.get("deletions") or 0
        lines = additions + deletions
        files = [f for f in nodes(pr, "files") if f]
        commits = []
        for c in nodes(pr, "commits"):
            commit = c.get("commit") or {}
            at = parse_ts(commit.get("committedDate") or commit.get("authoredDate"))
            sha = commit.get("oid")
            if sha and at:
                commits.append({"sha": sha, "at": at, "headline": commit.get("messageHeadline") or ""})
        commits.sort(key=lambda c: c["at"])
        reviews = bot_reviews(pr)
        lgtms = collect_lgtm_events(pr)
        first = lgtms[0] if lgtms else None
        first_at = first["at"] if first else None
        first_sha = first_lgtm_sha(pr) if first else None
        stands = lgtm_stands_by_sha(commits, reviews)
        approvals = human_approvals(pr)
        first_approval = approvals[0] if approvals else None
        dismissals = dismissal_count(pr)
        close = closed_info(pr)
        labels = [x.get("name") for x in nodes(pr, "labels") if x]
        first_commit_at = first_login.get(login)
        tenure_days = None
        if first_commit_at and created:
            tenure_days = (created - first_commit_at).total_seconds() / 86400.0
            if tenure_days < 0:
                tenure_days = 0.0
        bot_before = sum(1 for r in reviews if first_at and r["at"] < first_at)
        rereview = any(first_at and r["at"] > first_at and r.get("sha") and r.get("sha") != first_sha for r in reviews)
        # human comments on the PR (issue + threads), for engagement, computed later with labels
        human_inline = 0
        for thread in nodes(pr, "reviewThreads"):
            comments = (thread.get("comments") or {}).get("nodes") or []
            for c in comments:
                if not is_bot_author(c.get("author")) and not is_review_bot(c.get("author")):
                    human_inline += 1
        row = {
            "number": pr["number"],
            "url": pr.get("url"),
            "title": pr.get("title") or "",
            "body": pr.get("body") or "",
            "state": pr.get("state"),
            "is_draft": pr.get("isDraft"),
            "author": login,
            "author_type": author_type,
            "current_org_member": login in members,
            "author_tenure_days": tenure_days,
            "tenure_bucket": tenure_bucket(tenure_days),
            "author_first_commit": iso(first_commit_at),
            "created_at": iso(created),
            "merged_at": iso(merged),
            "closed_at": iso(closed),
            "month": month_key(created) if created else None,
            "in_cohort": in_cohort,
            "additions": additions,
            "deletions": deletions,
            "lines": lines,
            "size_bucket": size_bucket(lines),
            "changed_files": pr.get("changedFiles"),
            "top_dirs": top_dirs(files),
            "file_paths": [f.get("path") for f in files],
            "labels": labels,
            "merged": merged is not None,
            "merged_by": author_login(pr.get("mergedBy")),
            "merge_commit": (pr.get("mergeCommit") or {}).get("oid"),
            "head_sha": pr.get("headRefOid"),
            "closed_by": close["closed_by"],
            "closing_comment": close["closing_comment"],
            "bot_reviewed": bool(reviews),
            "bot_review_count": len(reviews),
            "bot_lgtm": first is not None,
            "first_lgtm_at": iso(first_at),
            "first_lgtm_sha": first_sha,
            "first_lgtm_exact": bool(first and first.get("exact")),
            "first_lgtm_kind": first.get("kind") if first else None,
            "first_lgtm_body": (first.get("body") if first else None),
            "bot_reviews_before_lgtm": bot_before if first else None,
            "bot_rereview_after_lgtm": rereview if first else None,
            "lgtm_stands_on_shas": [sha for sha, ok in stands.items() if ok],
            "commits": [{"sha": c["sha"], "at": iso(c["at"])} for c in commits],
            "first_human_approval_at": iso(first_approval["at"]) if first_approval else None,
            "first_human_approver": first_approval["login"] if first_approval else None,
            "human_approval_count": len(approvals),
            "human_approvals": [
                {"login": a["login"], "at": iso(a["at"]), "body": a["body"], "sha": a["sha"]} for a in approvals
            ],
            "human_reviews": [
                {
                    "login": author_login(rev.get("author")),
                    "state": rev.get("state"),
                    "at": rev.get("submittedAt"),
                    "body_empty": not (rev.get("body") or "").strip(),
                    "sha": (rev.get("commit") or {}).get("oid"),
                }
                for rev in nodes(pr, "reviews")
                if rev.get("author")
                and not is_bot_author(rev.get("author"))
                and not is_review_bot(rev.get("author"))
                and author_login(rev.get("author"))
            ],
            "review_dismissals": dismissals,
            "human_review_before_lgtm": human_activity_before(pr, first_at),
            "force_pushes": force_push_count(pr),
            "review_request_ats": [iso(t) for t in review_request_times(pr)],
            "human_inline_comments": human_inline,
            "open_to_lgtm_h": hours_between(created, first_at),
            "open_to_approval_h": hours_between(created, first_approval["at"] if first_approval else None),
            "lgtm_to_approval_h": hours_between(first_at, first_approval["at"] if first_approval else None),
            "lgtm_to_merge_h": hours_between(first_at, merged),
            "approval_to_merge_h": hours_between(first_approval["at"] if first_approval else None, merged),
            "approval_before_lgtm": bool(first_at and first_approval and first_approval["at"] < first_at),
        }
        pr_out.write(json.dumps(row, separators=(",", ":")) + "\n")
        if first and len(example_lgtm) < 12 and first.get("exact"):
            example_lgtm.append(
                {"number": pr["number"], "url": pr.get("url"), "at": iso(first_at), "body": first.get("body"), "kind": first.get("kind")}
            )
        if first and row["bot_reviews_before_lgtm"] is not None:
            bot_round_counts.append(row["bot_reviews_before_lgtm"])

        author_login_s = login
        findings = human_threads(pr) + human_review_bodies(pr)
        for finding in findings:
            link = link_change(finding, commits, author_login_s)
            timing = "no_lgtm"
            if first_at and finding["at"]:
                timing = "before" if finding["at"] < first_at else "after"
            finding_out.write(
                json.dumps(
                    {
                        "finding_id": finding["finding_id"],
                        "pr": pr["number"],
                        "pr_url": pr.get("url"),
                        "pr_author": author_login_s,
                        "month": row["month"],
                        "in_cohort": in_cohort,
                        "source": finding["source"],
                        "timing": timing,
                        "at": iso(finding["at"]),
                        "login": finding["login"],
                        "body": finding["body"],
                        "path": finding["path"],
                        "line": finding["line"],
                        "diff_hunk": (finding.get("diff_hunk") or "")[:4000],
                        "replies": finding["replies"],
                        "thread_resolved": finding["thread_resolved"],
                        "author_acknowledged": link["author_acknowledged"],
                        "later_commit_count": len(link["later_commit_shas"]),
                        "review_state": finding.get("review_state"),
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
        if n % 500 == 0:
            print(f"parsed {n}", flush=True)
    pr_out.close()
    finding_out.close()
    (INTERIM / "lgtm_examples.json").write_text(json.dumps(example_lgtm, indent=2))
    print(f"done {n} prs truncated_fields {truncated_n}", flush=True)


if __name__ == "__main__":
    main()
