#!/usr/bin/env bash
# Download Terraform Cloud speculative plan JSON for the current commit.
#
# Discovery: TFC posts GitHub *commit statuses* (context Terraform Cloud/...),
# not check runs. Run IDs are parsed from status target_url when present.
#
# Security notes (see docs/checkov.md):
# - GET /runs/:id/plan/json-output requires a user/team token with workspace
#   *admin* access. Organization tokens cannot call it.
# - That JSON can contain Terraform sensitive values in plaintext.
# - Prefer not enabling plan mode until redaction / privilege model is settled.
# - This script never prints plan contents; callers must not upload tfc-plans/.
set -euo pipefail

out_dir="${1:?output directory required}"
commit_sha="${2:?commit sha required}"
timeout_seconds="${3:-120}"
poll_seconds="${4:-15}"
tfc_host="${TFC_HOSTNAME:-app.terraform.io}"
# Use redacted endpoint when set (experimental; may still omit needed fields).
plan_endpoint="${TFC_PLAN_ENDPOINT:-json-output}"

mkdir -p "${out_dir}"
manifest="${out_dir}/manifest.txt"
: > "${manifest}"

write_output() {
  local key="$1"
  local value="$2"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "${key}=${value}" >> "${GITHUB_OUTPUT}"
  fi
}

summarize() {
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    cat >> "${GITHUB_STEP_SUMMARY}"
  fi
}

if [[ -z "${TFE_TOKEN:-}" ]]; then
  echo "TFE_TOKEN is not set; skipping TFC plan download."
  write_output skipped_reason missing_token
  write_output plan_count 0
  summarize <<EOF
## Checkov Terraform plan mode

Skipped: \`TFE_TOKEN\` is not configured. Static scans (if enabled) still run.
EOF
  exit 0
fi

if [[ -z "${GITHUB_TOKEN:-}" || -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "GITHUB_TOKEN / GITHUB_REPOSITORY required to discover TFC statuses."
  write_output skipped_reason missing_github_context
  write_output plan_count 0
  exit 0
fi

api() {
  curl -fsSL \
    --header "Authorization: Bearer ${TFE_TOKEN}" \
    --header "Content-Type: application/vnd.api+json" \
    "$@"
}

extract_run_ids_from_statuses() {
  # Status list is newest-first. unique_by keeps the first (newest) status per context
  # so a re-run does not leave a stale run id in the scan set.
  jq -r '
    .statuses
    | map(select(.context // "" | test("Terraform Cloud|HCP Terraform"; "i")))
    | unique_by(.context)
    | .[]
    | .target_url // empty
    | capture("/runs/(?<id>run-[A-Za-z0-9]+)")
    | .id
  ' 2>/dev/null | sort -u
}

deadline=$((SECONDS + timeout_seconds))
run_ids=""

echo "Waiting up to ${timeout_seconds}s for TFC commit statuses on ${commit_sha}..."

forbidden=false
while (( SECONDS < deadline )); do
  # List endpoint includes target_url; combined /status often nulls it out.
  if ! status_json="$(curl -fsSL \
    --header "Authorization: Bearer ${GITHUB_TOKEN}" \
    --header "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${GITHUB_REPOSITORY}/commits/${commit_sha}/statuses?per_page=100")"; then
    echo "::warning::Could not list commit statuses; retrying."
    sleep "${poll_seconds}"
    continue
  fi

  # Normalize array → {statuses: [...]} for the jq helper.
  status_json="$(printf '%s\n' "${status_json}" | jq '{statuses: .}')"

  run_ids="$(printf '%s\n' "${status_json}" | extract_run_ids_from_statuses || true)"

  if [[ -n "${run_ids}" ]]; then
    all_ready=true
    while IFS= read -r run_id; do
      [[ -z "${run_id}" ]] && continue
      status_code="$(curl -sS -o /dev/null -w '%{http_code}' \
        --header "Authorization: Bearer ${TFE_TOKEN}" \
        --header "Content-Type: application/vnd.api+json" \
        "https://${tfc_host}/api/v2/runs/${run_id}/plan/${plan_endpoint}" || echo "000")"
      if [[ "${status_code}" == "401" || "${status_code}" == "403" ]]; then
        echo "::warning::TFC plan download forbidden (HTTP ${status_code}) for ${run_id}. json-output requires workspace admin."
        forbidden=true
        all_ready=false
        break
      fi
      if [[ "${status_code}" == "204" || "${status_code}" == "404" || "${status_code}" == "000" ]]; then
        all_ready=false
        break
      fi
    done <<< "${run_ids}"

    if [[ "${forbidden}" == "true" ]]; then
      break
    fi
    if [[ "${all_ready}" == "true" ]]; then
      break
    fi
  fi

  sleep "${poll_seconds}"
done

if [[ "${forbidden}" == "true" ]]; then
  write_output skipped_reason forbidden
  write_output plan_count 0
  summarize <<EOF
## Checkov Terraform plan mode

Skipped: TFC returned 401/403 for plan JSON. \`json-output\` needs a user or team token with workspace admin.
EOF
  exit 0
fi

if [[ -z "${run_ids}" ]]; then
  echo "No TFC run IDs found for commit ${commit_sha} within timeout."
  echo "Note: combined /status often omits target_url; individual status API may be needed later."
  write_output skipped_reason no_runs
  write_output plan_count 0
  summarize <<EOF
## Checkov Terraform plan mode

No Terraform Cloud run IDs found for \`${commit_sha}\` within ${timeout_seconds}s (via commit statuses).
EOF
  exit 0
fi

plan_count=0
while IFS= read -r run_id; do
  [[ -z "${run_id}" ]] && continue

  workspace_dir="."
  run_json="$(api "https://${tfc_host}/api/v2/runs/${run_id}?include=workspace" || true)"
  if [[ -n "${run_json}" ]]; then
    workspace_dir="$(printf '%s\n' "${run_json}" | jq -r '
      (.included // [])
      | map(select(.type == "workspaces"))
      | .[0].attributes["working-directory"] // "."
    ')"
    [[ -z "${workspace_dir}" || "${workspace_dir}" == "null" ]] && workspace_dir="."
  fi

  plan_path="${out_dir}/${run_id}.json"
  http_code="$(curl -sS -L -o "${plan_path}" -w '%{http_code}' \
    --header "Authorization: Bearer ${TFE_TOKEN}" \
    --header "Content-Type: application/vnd.api+json" \
    "https://${tfc_host}/api/v2/runs/${run_id}/plan/${plan_endpoint}" || echo "000")"

  if [[ "${http_code}" != "200" ]]; then
    echo "Skipping ${run_id}: plan JSON not available (HTTP ${http_code}). Admin token may be required for json-output."
    rm -f "${plan_path}"
    continue
  fi

  if ! jq -e . "${plan_path}" >/dev/null 2>&1; then
    echo "Skipping ${run_id}: response was not valid JSON."
    rm -f "${plan_path}"
    continue
  fi

  echo "${run_id}|${plan_path}|${workspace_dir}" >> "${manifest}"
  plan_count=$((plan_count + 1))
  echo "Downloaded plan metadata for ${run_id} (working-directory=${workspace_dir}; endpoint=${plan_endpoint})"
done <<< "${run_ids}"

write_output plan_count "${plan_count}"
write_output manifest "${manifest}"
write_output plans_dir "${out_dir}"

summarize <<EOF
## Checkov Terraform plan mode

Downloaded **${plan_count}** TFC plan JSON file(s) for \`${commit_sha}\` via \`${plan_endpoint}\`.
Raw plan files are kept on the runner only for this job (not uploaded as artifacts).
EOF
