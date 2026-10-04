"""Cache foxglove/app pull requests opened on or after 2026-04-01.

Raw responses:
  data/raw/app/pulls_pages/page_NNNN.json
  data/raw/app/graphql/batch_NNNN.json
  data/raw/app/prs/<number>.json
  data/raw/app/meta/members.json
  data/raw/app/meta/rulesets.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from ghutil import GitHub, GitHubError

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "app"
PAGES = RAW / "pulls_pages"
GRAPHQL_DIR = RAW / "graphql"
PRS = RAW / "prs"
META = RAW / "meta"

WINDOW_START = "2026-04-01T00:00:00Z"
# Include PRs through today so Step 4 can see fix PRs opened after the cohort window.
# Cohort membership is decided later from createdAt.

PR_FRAGMENT = r"""
fragment Actor on Actor {
  ... on User { login __typename }
  ... on Bot { login __typename }
  ... on Organization { login __typename }
  ... on Mannequin { login __typename }
}
fragment Author on Actor {
  ... on User { login __typename }
  ... on Bot { login __typename }
  ... on Organization { login __typename }
  ... on Mannequin { login __typename }
}
fragment PRFields on PullRequest {
  number
  title
  body
  state
  isDraft
  createdAt
  updatedAt
  closedAt
  mergedAt
  additions
  deletions
  changedFiles
  baseRefName
  headRefName
  headRefOid
  url
  author { ...Author }
  mergedBy { ...Author }
  mergeCommit { oid }
  labels(first: 30) {
    pageInfo { hasNextPage endCursor }
    nodes { name }
  }
  files(first: 100) {
    pageInfo { hasNextPage endCursor }
    nodes { path additions deletions }
  }
  commits(first: 80) {
    pageInfo { hasNextPage endCursor }
    nodes {
      commit {
        oid
        committedDate
        authoredDate
        messageHeadline
        authors(first: 5) {
          nodes { name email user { login } }
        }
      }
    }
  }
  reviews(first: 50) {
    pageInfo { hasNextPage endCursor }
    nodes {
      databaseId
      state
      body
      submittedAt
      author { ...Author }
      commit { oid }
    }
  }
  comments(first: 60) {
    pageInfo { hasNextPage endCursor }
    nodes {
      databaseId
      body
      createdAt
      author { ...Author }
    }
  }
  reviewThreads(first: 50) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      isResolved
      isOutdated
      path
      line
      comments(first: 30) {
        pageInfo { hasNextPage endCursor }
        nodes {
          databaseId
          body
          createdAt
          path
          diffHunk
          line
          originalLine
          author { ...Author }
        }
      }
    }
  }
  timelineItems(
    first: 100
    itemTypes: [
      REVIEW_REQUESTED_EVENT
      REVIEW_REQUEST_REMOVED_EVENT
      HEAD_REF_FORCE_PUSHED_EVENT
      HEAD_REF_RESTORED_EVENT
      CLOSED_EVENT
      MERGED_EVENT
      REOPENED_EVENT
      READY_FOR_REVIEW_EVENT
      CONVERT_TO_DRAFT_EVENT
      REVIEW_DISMISSED_EVENT
      AUTOMATIC_BASE_CHANGE_SUCCEEDED_EVENT
      BASE_REF_CHANGED_EVENT
    ]
  ) {
    pageInfo { hasNextPage endCursor }
    nodes {
      __typename
      ... on ReviewRequestedEvent {
        createdAt
        actor { ...Actor }
        requestedReviewer {
          __typename
          ... on User { login }
          ... on Bot { login }
          ... on Team { name }
          ... on Mannequin { login }
        }
      }
      ... on ReviewRequestRemovedEvent {
        createdAt
        actor { ...Actor }
      }
      ... on HeadRefForcePushedEvent {
        createdAt
        actor { ...Actor }
        beforeCommit { oid }
        afterCommit { oid }
      }
      ... on HeadRefRestoredEvent {
        createdAt
        actor { ...Actor }
      }
      ... on ClosedEvent { createdAt actor { ...Actor } }
      ... on MergedEvent { createdAt actor { ...Actor } commit { oid } }
      ... on ReopenedEvent { createdAt actor { ...Actor } }
      ... on ReadyForReviewEvent { createdAt actor { ...Actor } }
      ... on ConvertToDraftEvent { createdAt actor { ...Actor } }
      ... on ReviewDismissedEvent { createdAt actor { ...Actor } dismissalMessage }
      ... on PullRequestCommit { commit { oid committedDate } }
      ... on AutomaticBaseChangeSucceededEvent { createdAt }
      ... on BaseRefChangedEvent { createdAt }
    }
  }
}
"""

BATCH_QUERY = (
    PR_FRAGMENT
    + """
query {
  rateLimit { cost remaining resetAt }
  repository(owner: "foxglove", name: "app") {
    %s
  }
}
"""
)


def save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":")))


def load(path: Path):
    return json.loads(path.read_text())


def fetch_pull_pages(gh: GitHub) -> list[int]:
    numbers: list[int] = []
    page = 1
    while True:
        path = PAGES / f"page_{page:04d}.json"
        if path.exists():
            payload = load(path)
            print(f"pulls page {page} cached ({len(payload)} prs)", flush=True)
        else:
            payload, _headers = gh.request(
                "GET",
                f"/repos/foxglove/app/pulls?state=all&sort=created&direction=desc&per_page=100&page={page}",
            )
            save(path, payload)
            print(f"pulls page {page} fetched ({len(payload)} prs)", flush=True)
        if not payload:
            break
        stop = False
        for pr in payload:
            created = pr.get("created_at") or ""
            if created < WINDOW_START:
                stop = True
                continue
            numbers.append(pr["number"])
        oldest = payload[-1].get("created_at")
        if stop or (oldest and oldest < WINDOW_START) or len(payload) < 100:
            break
        page += 1
        if page > 200:
            raise SystemExit("pull page walk exceeded 200 pages")
    # unique, preserve desc order
    seen = set()
    out = []
    for n in numbers:
        if n not in seen:
            seen.add(n)
            out.append(n)
    print(f"PR numbers since {WINDOW_START}: {len(out)}", flush=True)
    save(META / "pr_numbers.json", out)
    return out


def alias_block(number: int, alias: str) -> str:
    return f'{alias}: pullRequest(number: {number}) {{ ...PRFields }}'


def fetch_batch(gh: GitHub, numbers: list[int], batch_idx: int) -> dict[int, dict]:
    aliases = [f"p{i}" for i in range(len(numbers))]
    selection = "\n".join(alias_block(n, a) for n, a in zip(numbers, aliases))
    query = BATCH_QUERY % selection
    data = gh.graphql(query)
    raw_path = GRAPHQL_DIR / f"batch_{batch_idx:05d}.json"
    save(raw_path, data)
    if data.get("errors"):
        # Keep going if data is present; log a short count.
        print(f"batch {batch_idx} partial errors: {len(data['errors'])}", flush=True)
    repo = (data.get("data") or {}).get("repository") or {}
    limit = (data.get("data") or {}).get("rateLimit") or {}
    print(
        f"batch {batch_idx} n={len(numbers)} cost={limit.get('cost')} remaining={limit.get('remaining')}",
        flush=True,
    )
    out = {}
    for n, a in zip(numbers, aliases):
        pr = repo.get(a)
        if pr:
            out[n] = pr
    return out


def paginate_connection(gh: GitHub, number: int, field: str, inner: str, cursor: str, extra_args: str = "") -> dict:
    query = f"""
    query($cursor: String!) {{
      rateLimit {{ cost remaining resetAt }}
      repository(owner: "foxglove", name: "app") {{
        pullRequest(number: {number}) {{
          {field}(first: 50, after: $cursor{extra_args}) {{
            pageInfo {{ hasNextPage endCursor }}
            nodes {{ {inner} }}
          }}
        }}
      }}
    }}
    """
    data = gh.graphql(query, {"cursor": cursor})
    node = (((data.get("data") or {}).get("repository") or {}).get("pullRequest") or {}).get(field)
    return node or {"pageInfo": {"hasNextPage": False}, "nodes": []}


REVIEW_NODE = """
databaseId
state
body
submittedAt
author { ... on User { login __typename } ... on Bot { login __typename } }
commit { oid }
"""

COMMIT_NODE = """
commit { oid committedDate authoredDate messageHeadline authors(first: 5) { nodes { name email user { login } } } }
"""

FILE_NODE = "path additions deletions"
COMMENT_NODE = "databaseId body createdAt author { ... on User { login __typename } ... on Bot { login __typename } }"
_ACTOR = "actor { ... on User { login __typename } ... on Bot { login __typename } }"
TIMELINE_NODE = f"""
__typename
... on ReviewRequestedEvent {{ createdAt {_ACTOR} }}
... on ReviewRequestRemovedEvent {{ createdAt {_ACTOR} }}
... on HeadRefForcePushedEvent {{ createdAt {_ACTOR} beforeCommit {{ oid }} afterCommit {{ oid }} }}
... on HeadRefRestoredEvent {{ createdAt {_ACTOR} }}
... on ClosedEvent {{ createdAt {_ACTOR} }}
... on MergedEvent {{ createdAt {_ACTOR} commit {{ oid }} }}
... on ReopenedEvent {{ createdAt {_ACTOR} }}
... on ReadyForReviewEvent {{ createdAt {_ACTOR} }}
... on ConvertToDraftEvent {{ createdAt {_ACTOR} }}
... on ReviewDismissedEvent {{ createdAt {_ACTOR} dismissalMessage }}
... on PullRequestCommit {{ commit {{ oid committedDate }} }}
... on AutomaticBaseChangeSucceededEvent {{ createdAt }}
... on BaseRefChangedEvent {{ createdAt }}
"""

THREAD_COMMENT_NODE = (
    "databaseId body createdAt path diffHunk line originalLine "
    "author { ... on User { login __typename } ... on Bot { login __typename } }"
)


def extend_thread_comments(gh: GitHub, number: int, pr: dict) -> None:
    for thread in ((pr.get("reviewThreads") or {}).get("nodes") or []):
        comments = thread.get("comments") or {}
        nodes = list(comments.get("nodes") or [])
        page = comments.get("pageInfo") or {}
        thread_id = thread.get("id")
        guard = 0
        while page.get("hasNextPage") and page.get("endCursor") and thread_id and guard < 10:
            guard += 1
            query = f"""
            query($id: ID!, $cursor: String!) {{
              rateLimit {{ cost remaining resetAt }}
              node(id: $id) {{
                ... on PullRequestReviewThread {{
                  comments(first: 50, after: $cursor) {{
                    pageInfo {{ hasNextPage endCursor }}
                    nodes {{ {THREAD_COMMENT_NODE} }}
                  }}
                }}
              }}
            }}
            """
            data = gh.graphql(query, {"id": thread_id, "cursor": page["endCursor"]})
            block = ((data.get("data") or {}).get("node") or {}).get("comments") or {}
            nodes.extend(block.get("nodes") or [])
            page = block.get("pageInfo") or {"hasNextPage": False}
        thread["comments"] = {"pageInfo": page, "nodes": nodes}


def note_truncation(pr: dict) -> None:
    truncated = []
    for field in ("reviews", "commits", "files", "comments", "reviewThreads", "labels", "timelineItems"):
        page = (pr.get(field) or {}).get("pageInfo") or {}
        if page.get("hasNextPage"):
            truncated.append(field)
    more_threads = 0
    for thread in ((pr.get("reviewThreads") or {}).get("nodes") or []):
        if ((thread.get("comments") or {}).get("pageInfo") or {}).get("hasNextPage"):
            more_threads += 1
    pr["_truncated_fields"] = truncated
    pr["_threads_with_more_comments"] = more_threads


THREAD_NODE = """
id isResolved isOutdated path line
comments(first: 30) {
  pageInfo { hasNextPage endCursor }
  nodes { databaseId body createdAt path diffHunk line originalLine author { ... on User { login __typename } ... on Bot { login __typename } } }
}
"""


def extend_pages(gh: GitHub, number: int, pr: dict) -> None:
    specs = [
        ("reviews", REVIEW_NODE),
        ("commits", COMMIT_NODE),
        ("files", FILE_NODE),
        ("comments", COMMENT_NODE),
        ("reviewThreads", THREAD_NODE),
        ("labels", "name", ""),
        (
            "timelineItems",
            TIMELINE_NODE,
            ", itemTypes: [REVIEW_REQUESTED_EVENT, REVIEW_REQUEST_REMOVED_EVENT, HEAD_REF_FORCE_PUSHED_EVENT, HEAD_REF_RESTORED_EVENT, CLOSED_EVENT, MERGED_EVENT, REOPENED_EVENT, READY_FOR_REVIEW_EVENT, CONVERT_TO_DRAFT_EVENT, REVIEW_DISMISSED_EVENT, AUTOMATIC_BASE_CHANGE_SUCCEEDED_EVENT, BASE_REF_CHANGED_EVENT]",
        ),
    ]
    for field, inner, *rest in specs:
        extra_args = rest[0] if rest else ""
        conn = pr.get(field) or {}
        nodes = list(conn.get("nodes") or [])
        page = conn.get("pageInfo") or {}
        guard = 0
        while page.get("hasNextPage") and page.get("endCursor") and guard < 20:
            guard += 1
            nxt = paginate_connection(gh, number, field, inner, page["endCursor"], extra_args)
            nodes.extend(nxt.get("nodes") or [])
            page = nxt.get("pageInfo") or {"hasNextPage": False}
            save(
                GRAPHQL_DIR / f"page_{number}_{field}_{guard}.json",
                {"number": number, "field": field, "page": nxt},
            )
        if conn is not None:
            pr[field] = {"pageInfo": page, "nodes": nodes}


def fetch_meta(gh: GitHub) -> None:
    META.mkdir(parents=True, exist_ok=True)
    members_path = META / "members.json"
    if not members_path.exists():
        members = []
        page = 1
        while True:
            batch, headers = gh.request("GET", f"/orgs/foxglove/members?per_page=100&page={page}")
            members.extend(batch)
            link = headers.get("link") or ""
            if 'rel="next"' not in link or not batch:
                break
            page += 1
        save(members_path, members)
        print(f"org members {len(members)}", flush=True)
    rules_path = META / "rulesets.json"
    if not rules_path.exists():
        rulesets, _ = gh.request("GET", "/repos/foxglove/app/rulesets")
        detailed = []
        for rs in rulesets:
            full, _ = gh.request("GET", f"/repos/foxglove/app/rulesets/{rs['id']}")
            detailed.append(full)
        save(rules_path, detailed)
        print(f"rulesets {len(detailed)}", flush=True)


def main() -> None:
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    batch_size = 12
    if "--batch-size" in sys.argv:
        batch_size = int(sys.argv[sys.argv.index("--batch-size") + 1])
    gh = GitHub()
    for d in (PAGES, GRAPHQL_DIR, PRS, META):
        d.mkdir(parents=True, exist_ok=True)
    fetch_meta(gh)
    numbers = fetch_pull_pages(gh)
    if limit:
        numbers = numbers[:limit]
    pending = [n for n in numbers if not (PRS / f"{n}.json").exists()]
    print(f"pending detail fetch: {len(pending)}", flush=True)
    batch_idx = len(list(GRAPHQL_DIR.glob("batch_*.json")))
    started = time.time()
    done = 0
    for i in range(0, len(pending), batch_size):
        chunk = pending[i : i + batch_size]
        try:
            got = fetch_batch(gh, chunk, batch_idx)
        except GitHubError as exc:
            print(f"batch failed ({exc}); splitting", flush=True)
            got = {}
            for n in chunk:
                try:
                    got.update(fetch_batch(gh, [n], batch_idx))
                except GitHubError as one_exc:
                    print(f"PR {n} failed: {one_exc}", flush=True)
                    save(PRS / f"{n}.error.json", {"error": str(one_exc)})
                batch_idx += 1
        else:
            batch_idx += 1
        for n, pr in got.items():
            try:
                extend_pages(gh, n, pr)
                extend_thread_comments(gh, n, pr)
            except GitHubError as exc:
                print(f"pagination failed for {n}: {exc}", flush=True)
                save(PRS / f"{n}.error.json", {"error": str(exc)})
                continue
            note_truncation(pr)
            save(PRS / f"{n}.json", pr)
        done += len(chunk)
        elapsed = time.time() - started
        rate = done / elapsed if elapsed else 0
        print(f"progress {done}/{len(pending)} ({rate:.2f} pr/s)", flush=True)


if __name__ == "__main__":
    main()
