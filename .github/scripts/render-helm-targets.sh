#!/usr/bin/env bash
# Render Helm charts with per-environment target values into a directory for
# Checkov kubernetes scanning.
#
# Layouts:
#   sibling  — charts_root/*/chart + charts_root/*/targets/**/*.yaml  (infra)
#   shared   — chart_dirs (comma-separated) + targets_dir/*.yaml     (app, data-platform)
set -euo pipefail

layout="${1:?layout required (sibling|shared)}"
out_dir="${2:?output directory required}"
shift 2

# SOFT_FAIL=true (default): render failures are warnings and the script exits 0.
# SOFT_FAIL=false: any render failure or zero successful renders exits 1.
soft_fail="${SOFT_FAIL:-true}"
# Optional comma-separated helm --set pairs (e.g. key=placeholder).
helm_set="${HELM_SET:-}"
# Optional comma-separated globs matched against target file basenames.
exclude_targets="${EXCLUDE_TARGETS:-}"
# Render at most N targets per directory (sorted); 0 renders all.
max_targets_per_dir="${MAX_TARGETS_PER_DIR:-0}"
if ! [[ "${max_targets_per_dir}" =~ ^[0-9]+$ ]]; then
  echo "::error::max_targets_per_dir must be a non-negative integer, got '${max_targets_per_dir}'"
  exit 1
fi
# Optional bash ERE; the cap applies per directory per matched substring of the
# target basename. Non-matching targets share one "other" group.
target_group_pattern="${TARGET_GROUP_PATTERN:-}"
if [[ -n "${target_group_pattern}" ]]; then
  regex_rc=0
  # [[ =~ ]] returns 2 for an invalid regex.
  # shellcheck disable=SC2319
  [[ "" =~ ${target_group_pattern} ]] || regex_rc=$?
  if [[ "${regex_rc}" -eq 2 ]]; then
    echo "::error::target_group_pattern is not a valid bash regex: '${target_group_pattern}'"
    exit 1
  fi
fi

mkdir -p "${out_dir}"
render_count=0
fail_count=0
excluded_count=0
capped_count=0
skipped_targets=()

exclude_globs=()
if [[ -n "${exclude_targets}" ]]; then
  IFS=',' read -r -a raw_globs <<< "${exclude_targets}"
  for glob in "${raw_globs[@]}"; do
    glob="$(echo "${glob}" | xargs)"
    [[ -n "${glob}" ]] && exclude_globs+=("${glob}")
  done
fi

is_excluded() {
  local name
  name="$(basename "$1")"
  local glob
  for glob in "${exclude_globs[@]+"${exclude_globs[@]}"}"; do
    # shellcheck disable=SC2053 # glob match is intended
    if [[ "${name}" == ${glob} ]]; then
      return 0
    fi
  done
  return 1
}

# Sets selected_targets to the sorted target files under $1 (searched to depth
# $2, empty for unlimited), applying exclude_targets and max_targets_per_dir.
select_targets() {
  local root="$1"
  local depth_args=()
  [[ -n "${2:-}" ]] && depth_args=(-maxdepth "$2")
  local -A per_dir=()
  local values_file group
  selected_targets=()
  while IFS= read -r -d '' values_file; do
    if is_excluded "${values_file}"; then
      excluded_count=$((excluded_count + 1))
      skipped_targets+=("${values_file} (exclude_targets)")
      echo "Skipping ${values_file} (exclude_targets)"
      continue
    fi
    group="$(dirname "${values_file}")"
    if [[ -n "${target_group_pattern}" ]]; then
      if [[ "$(basename "${values_file}")" =~ ${target_group_pattern} ]]; then
        group="${group}|${BASH_REMATCH[0]}"
      else
        group="${group}|other"
      fi
    fi
    per_dir["${group}"]=$(( ${per_dir["${group}"]:-0} + 1 ))
    if [[ "${max_targets_per_dir}" -gt 0 && "${per_dir["${group}"]}" -gt "${max_targets_per_dir}" ]]; then
      capped_count=$((capped_count + 1))
      skipped_targets+=("${values_file} (max_targets_per_dir)")
      echo "Skipping ${values_file} (max_targets_per_dir=${max_targets_per_dir})"
      continue
    fi
    selected_targets+=("${values_file}")
  done < <(find "${root}" "${depth_args[@]+"${depth_args[@]}"}" -type f \( -name '*.yaml' -o -name '*.yml' \) -print0 | sort -z)
}

helm_set_args=()
if [[ -n "${helm_set}" ]]; then
  IFS=',' read -r -a helm_sets <<< "${helm_set}"
  for pair in "${helm_sets[@]}"; do
    pair="$(echo "${pair}" | xargs)"
    [[ -n "${pair}" ]] || continue
    helm_set_args+=(--set "${pair}")
  done
fi

build_deps() {
  local chart_dir="$1"
  if [[ ! -f "${chart_dir}/Chart.lock" ]]; then
    return 0
  fi
  local err
  err="$(mktemp)"
  if helm dependency build "${chart_dir}" >"${err}" 2>&1; then
    rm -f "${err}"
    return 0
  fi
  echo "::warning::helm dependency build failed for ${chart_dir}; trying update"
  cat "${err}" >&2 || true
  if helm dependency update "${chart_dir}" >"${err}" 2>&1; then
    rm -f "${err}"
    return 0
  fi
  echo "::warning::helm dependency update failed for ${chart_dir}"
  cat "${err}" >&2 || true
  rm -f "${err}"
}

render_one() {
  local chart_dir="$1"
  local values_file="$2"
  local release_name="$3"
  local dest="$4"

  mkdir -p "${dest}"
  if helm template "${release_name}" "${chart_dir}" \
    --values "${values_file}" \
    "${helm_set_args[@]}" \
    --output-dir "${dest}" \
    >/dev/null 2>"${dest}/.helm-stderr"; then
    render_count=$((render_count + 1))
    rm -f "${dest}/.helm-stderr"
  else
    fail_count=$((fail_count + 1))
    echo "::warning::helm template failed for ${chart_dir} + ${values_file}"
    cat "${dest}/.helm-stderr" >&2 || true
  fi
}

case "${layout}" in
  sibling)
    charts_root="${1:?charts_root required for sibling layout}"
    while IFS= read -r -d '' chart_dir; do
      chart_name="$(basename "$(dirname "${chart_dir}")")"
      targets_root="$(dirname "${chart_dir}")/targets"
      [[ -d "${targets_root}" ]] || continue
      build_deps "${chart_dir}"
      select_targets "${targets_root}" ""
      for values_file in "${selected_targets[@]+"${selected_targets[@]}"}"; do
        rel="${values_file#"${targets_root}/"}"
        safe_rel="${rel//\//__}"
        safe_rel="${safe_rel%.yaml}"
        dest="${out_dir}/${chart_name}/${safe_rel}"
        render_one "${chart_dir}" "${values_file}" "${chart_name}" "${dest}"
      done
    done < <(find "${charts_root}" -mindepth 2 -maxdepth 2 -type d -name chart -print0 | sort -z)
    ;;
  shared)
    chart_dirs_csv="${1:?chart_dirs required for shared layout}"
    targets_dir="${2:?targets_dir required for shared layout}"
    IFS=',' read -r -a chart_dirs <<< "${chart_dirs_csv}"
    for chart_dir in "${chart_dirs[@]}"; do
      chart_dir="$(echo "${chart_dir}" | xargs)"
      [[ -n "${chart_dir}" && -d "${chart_dir}" ]] || continue
      build_deps "${chart_dir}"
    done
    select_targets "${targets_dir}" 1
    for values_file in "${selected_targets[@]+"${selected_targets[@]}"}"; do
      target_name="$(basename "${values_file}")"
      target_name="${target_name%.yaml}"
      target_name="${target_name%.yml}"
      for chart_dir in "${chart_dirs[@]}"; do
        chart_dir="$(echo "${chart_dir}" | xargs)"
        [[ -n "${chart_dir}" && -d "${chart_dir}" ]] || continue
        chart_name="$(basename "${chart_dir}")"
        dest="${out_dir}/${chart_name}/${target_name}"
        render_one "${chart_dir}" "${values_file}" "${chart_name}" "${dest}"
      done
    done
    ;;
  *)
    echo "Unknown layout '${layout}'" >&2
    exit 1
    ;;
esac

echo "render_count=${render_count}" >> "${GITHUB_OUTPUT:-/dev/null}"
echo "fail_count=${fail_count}" >> "${GITHUB_OUTPUT:-/dev/null}"
echo "out_dir=${out_dir}" >> "${GITHUB_OUTPUT:-/dev/null}"

{
  echo "## Helm render for Checkov"
  echo
  echo "- Layout: \`${layout}\`"
  echo "- Rendered successfully: **${render_count}**"
  echo "- Render failures: **${fail_count}**"
  echo "- Targets excluded by \`exclude_targets\`: ${excluded_count}"
  echo "- Targets skipped by \`max_targets_per_dir\`: ${capped_count}"
  if [[ "${#skipped_targets[@]}" -gt 0 ]]; then
    echo
    echo "<details><summary>Skipped targets</summary>"
    echo
    # shellcheck disable=SC2016 # literal Markdown backticks
    printf -- '- `%s`\n' "${skipped_targets[@]}"
    echo
    echo "</details>"
  fi
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}"

counts="ok=${render_count}, failed=${fail_count}, excluded=${excluded_count}, capped=${capped_count}"
if [[ "${render_count}" -eq 0 && "${fail_count}" -eq 0 ]]; then
  counts="${counts}; no targets selected, check exclude_targets and the target paths"
fi

if [[ "${soft_fail}" == "true" ]]; then
  if [[ "${render_count}" -eq 0 || "${fail_count}" -gt 0 ]]; then
    echo "::warning::Helm render incomplete (${counts}). soft_fail=true, continuing."
  fi
  exit 0
fi

if [[ "${render_count}" -eq 0 || "${fail_count}" -gt 0 ]]; then
  echo "Helm render failed (${counts})." >&2
  exit 1
fi
