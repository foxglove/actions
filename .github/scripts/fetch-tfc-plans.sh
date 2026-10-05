#!/usr/bin/env bash
# Download Terraform Cloud speculative plan JSON for the current commit.
# Discovers run IDs from GitHub check runs posted by the TFC GitHub App, then
# fetches plan JSON via the TFC API. Soft-skips when the token is missing or
# no plans are ready within the timeout.
set -euo pipefail

out_dir="${1:?output directory required}"
commit_sha="${2:?commit sha required}"
timeout_seconds="${3:-600}"
poll_seconds="${4:-15}"
tfc_host="${TFC_HOSTNAME:-app.terraform.io}"

mkdir -p "${out_dir}"
manifest="${out_dir}/manifest.txt"
: > "${manifest}"

if [[ -z "${TFE_TOKEN:-}" ]]; then
  echo "TFE_TOKEN is not set; skipping TFC plan download."
  echo "skipped_reason=missing_token" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "plan_count=0" >> "${GITHUB_OUTPUT:-/dev/null}"
  {
    echo "## Checkov Terraform plan mode"
    echo
    echo "Skipped: \`TFE_TOKEN\` is not configured. Static scans (if enabled) still run."
  } >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
  exit 0
fi

if [[ -z "${GITHUB_TOKEN:-}" || -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "GITHUB_TOKEN / GITHUB_REPOSITORY required to discover TFC check runs."
  echo "skipped_reason=missing_github_context" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "plan_count=0" >> "${GITHUB_OUTPUT:-/dev/null}"
  exit 0
fi

api() {
  curl -fsSL \
    --header "Authorization: Bearer ${TFE_TOKEN}" \
    --header "Content-Type: application/vnd.api+json" \
    "$@"
}

extract_run_ids() {
  # Prefer details_url / html_url that contain /runs/run-...
  jq -r '
    .check_runs[]?
    | select(
        (.app.slug // "" | test("terraform"; "i"))
        or (.name // "" | test("Terraform Cloud|HCP Terraform"; "i"))
      )
    | [.details_url // empty, .html_url // empty]
    | .[]
    | capture("/runs/(?<id>run-[A-Za-z0-9]+)")
    | .id
  ' 2>/dev/null | sort -u
}

deadline=$((SECONDS + timeout_seconds))
run_ids=""

echo "Waiting up to ${timeout_seconds}s for TFC check runs on ${commit_sha}..."

while (( SECONDS < deadline )); do
  checks_json="$(curl -fsSL \
    --header "Authorization: Bearer ${GITHUB_TOKEN}" \
    --header "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${GITHUB_REPOSITORY}/commits/${commit_sha}/check-runs?per_page=100")"

  run_ids="$(printf '%s\n' "${checks_json}" | extract_run_ids || true)"

  if [[ -n "${run_ids}" ]]; then
    # Wait until each run's plan is downloadable (not 204).
    all_ready=true
    while IFS= read -r run_id; do
      [[ -z "${run_id}" ]] && continue
      status_code="$(curl -sS -o /dev/null -w '%{http_code}' \
        --header "Authorization: Bearer ${TFE_TOKEN}" \
        --header "Content-Type: application/vnd.api+json" \
        "https://${tfc_host}/api/v2/runs/${run_id}/plan/json-output" || echo "000")"
      if [[ "${status_code}" == "204" || "${status_code}" == "404" || "${status_code}" == "000" ]]; then
        all_ready=false
        break
      fi
    done <<< "${run_ids}"

    if [[ "${all_ready}" == "true" ]]; then
      break
    fi
  fi

  sleep "${poll_seconds}"
done

if [[ -z "${run_ids}" ]]; then
  echo "No TFC run IDs found for commit ${commit_sha} within timeout."
  echo "skipped_reason=no_runs" >> "${GITHUB_OUTPUT:-/dev/null}"
  echo "plan_count=0" >> "${GITHUB_OUTPUT:-/dev/null}"
  {
    echo "## Checkov Terraform plan mode"
    echo
    echo "No Terraform Cloud speculative plans found for \`${commit_sha}\` within ${timeout_seconds}s."
  } >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
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
    "https://${tfc_host}/api/v2/runs/${run_id}/plan/json-output" || echo "000")"

  if [[ "${http_code}" != "200" ]]; then
    echo "Skipping ${run_id}: plan JSON not available (HTTP ${http_code})."
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
  echo "Downloaded plan for ${run_id} (working-directory=${workspace_dir})"
done <<< "${run_ids}"

echo "plan_count=${plan_count}" >> "${GITHUB_OUTPUT:-/dev/null}"
echo "manifest=${manifest}" >> "${GITHUB_OUTPUT:-/dev/null}"
echo "plans_dir=${out_dir}" >> "${GITHUB_OUTPUT:-/dev/null}"

{
  echo "## Checkov Terraform plan mode"
  echo
  echo "Downloaded **${plan_count}** TFC plan JSON file(s) for \`${commit_sha}\`."
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
