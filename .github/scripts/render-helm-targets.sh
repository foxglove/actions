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

mkdir -p "${out_dir}"
render_count=0
fail_count=0

render_one() {
  local chart_dir="$1"
  local values_file="$2"
  local release_name="$3"
  local dest="$4"

  mkdir -p "${dest}"
  if helm template "${release_name}" "${chart_dir}" \
    --values "${values_file}" \
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
      # Prefer vendored chart deps when present.
      if [[ -f "${chart_dir}/Chart.lock" ]]; then
        helm dependency build "${chart_dir}" >/dev/null 2>&1 || \
          helm dependency update "${chart_dir}" >/dev/null 2>&1 || true
      fi
      while IFS= read -r -d '' values_file; do
        rel="${values_file#"${targets_root}/"}"
        safe_rel="${rel//\//__}"
        safe_rel="${safe_rel%.yaml}"
        dest="${out_dir}/${chart_name}/${safe_rel}"
        render_one "${chart_dir}" "${values_file}" "${chart_name}" "${dest}"
      done < <(find "${targets_root}" -type f \( -name '*.yaml' -o -name '*.yml' \) -print0 | sort -z)
    done < <(find "${charts_root}" -mindepth 2 -maxdepth 2 -type d -name chart -print0 | sort -z)
    ;;
  shared)
    chart_dirs_csv="${1:?chart_dirs required for shared layout}"
    targets_dir="${2:?targets_dir required for shared layout}"
    IFS=',' read -r -a chart_dirs <<< "${chart_dirs_csv}"
    while IFS= read -r -d '' values_file; do
      target_name="$(basename "${values_file}")"
      target_name="${target_name%.yaml}"
      target_name="${target_name%.yml}"
      for chart_dir in "${chart_dirs[@]}"; do
        chart_dir="$(echo "${chart_dir}" | xargs)"
        [[ -n "${chart_dir}" && -d "${chart_dir}" ]] || continue
        chart_name="$(basename "${chart_dir}")"
        if [[ -f "${chart_dir}/Chart.lock" ]]; then
          helm dependency build "${chart_dir}" >/dev/null 2>&1 || \
            helm dependency update "${chart_dir}" >/dev/null 2>&1 || true
        fi
        dest="${out_dir}/${chart_name}/${target_name}"
        render_one "${chart_dir}" "${values_file}" "${chart_name}" "${dest}"
      done
    done < <(find "${targets_dir}" -maxdepth 1 -type f \( -name '*.yaml' -o -name '*.yml' \) -print0 | sort -z)
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
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}"

if [[ "${render_count}" -eq 0 ]]; then
  echo "No charts were rendered; nothing to scan." >&2
  exit 1
fi
