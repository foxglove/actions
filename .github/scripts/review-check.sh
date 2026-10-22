#!/usr/bin/env bash
# Read this pull request's beefcake review and run review-verdict.py.
#
# Extra arguments are passed to review-verdict.py, such as --accept-earlier.
# VERDICT_MODE=prior always exits 0. On an LGTM verdict it sets skip=true so a
# rerun can keep the check green without posting another review. The default
# mode exits 0, 1, or 2 and sets lgtm=true when the verdict is LGTM.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
script="${here}/review-verdict.py"

finish_fail() {
  if [ "${VERDICT_MODE:-}" = "prior" ]; then
    exit 0
  fi
  exit 1
}

if [ ! -f "$script" ]; then
  echo "Missing review verdict script: $script" >&2
  finish_fail
fi

jobs_file="$(mktemp)"
reviews_file="$(mktemp)"
comments_file="$(mktemp)"
issue_comments_file="$(mktemp)"
threads_file="$(mktemp)"
trap 'rm -f "$jobs_file" "$reviews_file" "$comments_file" "$issue_comments_file" "$threads_file"' EXIT

gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}/jobs?per_page=100" > "$jobs_file"
owner="${GITHUB_REPOSITORY%%/*}"
repo_name="${GITHUB_REPOSITORY#*/}"
thread_query="$(cat <<'GRAPHQL'
query($owner:String!, $name:String!, $number:Int!, $cursor:String) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          comments(first:1) {
            nodes { author { login } body }
          }
        }
      }
    }
  }
}
GRAPHQL
)"

record_lgtm() {
  local message="$1"
  if [ "$message" != "The beefcake review on this commit is LGTM." ]; then
    return 0
  fi
  if [ "${VERDICT_MODE:-}" = "prior" ]; then
    echo "skip=true" >> "$GITHUB_OUTPUT"
  else
    echo "lgtm=true" >> "$GITHUB_OUTPUT"
  fi
}

attempt=1
while [ "$attempt" -le 6 ]; do
  gh api --paginate "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews?per_page=100" > "$reviews_file"
  gh api --paginate "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/comments?per_page=100" > "$comments_file"
  # Conversation comments need the issues permission. The job token may not
  # have it. A review body or review comment that is LGTM still counts.
  if ! gh api --paginate "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments?per_page=100" > "$issue_comments_file"; then
    echo "::notice::Could not read conversation comments. An LGTM review body or review comment still counts."
    echo "[]" > "$issue_comments_file"
  fi
  threads='[]'
  cursor=""
  page_number=0
  while [ "$page_number" -lt 10 ]; do
    if [ -z "$cursor" ]; then
      page="$(gh api graphql -f query="$thread_query" -f owner="$owner" -f name="$repo_name" -F number="$PR_NUMBER")"
    else
      page="$(gh api graphql -f query="$thread_query" -f owner="$owner" -f name="$repo_name" -F number="$PR_NUMBER" -f cursor="$cursor")"
    fi
    if jq -e '(.errors // []) | length > 0' >/dev/null <<< "$page"; then
      echo "Could not read review threads." >&2
      jq -r '.errors[]?.message' <<< "$page" >&2
      finish_fail
    fi
    nodes="$(jq -c '.data.repository.pullRequest.reviewThreads.nodes // []' <<< "$page")"
    threads="$(jq -c --argjson nodes "$nodes" '. + $nodes' <<< "$threads")"
    has_next="$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage' <<< "$page")"
    if [ "$has_next" != "true" ]; then
      break
    fi
    cursor="$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // empty' <<< "$page")"
    page_number=$((page_number + 1))
  done
  printf '%s\n' "$threads" > "$threads_file"
  set +e
  message="$(python3 "$script" \
    --jobs "$jobs_file" \
    --job-name "$GITHUB_JOB" \
    --reviews "$reviews_file" \
    --comments "$comments_file" \
    --issue-comments "$issue_comments_file" \
    --threads "$threads_file" \
    --head-sha "$HEAD_SHA" \
    --bot "$BOT_LOGIN" \
    "$@" 2>&1)"
  status=$?
  set -e
  echo "$message"
  if [ "$status" -eq 0 ]; then
    echo "$message" >> "$GITHUB_STEP_SUMMARY"
    record_lgtm "$message"
    exit 0
  fi
  if [ "$status" -ne 2 ] || [ "$attempt" -eq 6 ]; then
    echo "$message" >> "$GITHUB_STEP_SUMMARY"
    finish_fail
  fi
  echo "The review is not on this commit yet. Waiting."
  attempt=$((attempt + 1))
  sleep 5
done
finish_fail
