#!/usr/bin/env bash
# One image scan writes JSON. Table and SARIF are converted from that file so
# the three outputs match. --exit-code is applied on the table convert:
# 0 when SOFT_FAIL=true, 1 otherwise. A missing image, a failed docker load,
# or any other Trivy exit still fails the job.
# Trivy 0.76 defaults to vuln+secret; --scanners vuln keeps the secret scanner off.
set -euo pipefail

: "${IMAGES:?images input is required}"
: "${SOFT_FAIL:?}"
: "${SEVERITY:?}"
: "${IGNORE_UNFIXED:?}"
: "${CONFIG_FILE:?Trivy config was not resolved}"
: "${TRIVY_IMAGE:?}"
: "${TRIVY_TIMEOUT:?}"
IGNORE_FILE="${IGNORE_FILE:-}"
IMAGE_ARTIFACT="${IMAGE_ARTIFACT:-}"
ARTIFACT_SUFFIX="${ARTIFACT_SUFFIX:-default}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "::error::Trivy config '${CONFIG_FILE}' does not exist." >&2
  exit 1
fi

ignore_args=()
if [[ -n "${IGNORE_FILE}" ]]; then
  if [[ ! -f "${IGNORE_FILE}" ]]; then
    echo "::error::ignore_file '${IGNORE_FILE}' does not exist." >&2
    exit 1
  fi
  ignore_args=(--ignorefile "${IGNORE_FILE}")
fi

if [[ "${SOFT_FAIL}" == "true" ]]; then
  exit_code=0
else
  exit_code=1
fi

mkdir -p trivy-results .trivy-cache

if [[ -n "${IMAGE_ARTIFACT}" ]]; then
  if [[ ! -d trivy-image-artifact ]]; then
    echo "::error::image_artifact '${IMAGE_ARTIFACT}' was not downloaded." >&2
    exit 1
  fi
  loaded=0
  while IFS= read -r -d '' tarball; do
    loaded=1
    echo "docker load ${tarball}"
    docker load -i "${tarball}"
  done < <(find trivy-image-artifact -type f -print0 | sort -z)
  if [[ "${loaded}" -eq 0 ]]; then
    echo "::error::image_artifact '${IMAGE_ARTIFACT}' contains no files." >&2
    exit 1
  fi
fi

images=()
IFS=',' read -r -a raw_images <<< "${IMAGES}"
for raw in "${raw_images[@]}"; do
  image="${raw#"${raw%%[![:space:]]*}"}"
  image="${image%"${image##*[![:space:]]}"}"
  if [[ -z "${image}" ]]; then
    echo "::error::images contains an empty entry." >&2
    exit 1
  fi
  if [[ "${image}" == *..* || ! "${image}" =~ ^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$ ]]; then
    echo "::error::images entry '${image}' is not a local image reference." >&2
    exit 1
  fi
  images+=("${image}")
done

if [[ "${#images[@]}" -eq 0 ]]; then
  echo "::error::images is empty." >&2
  exit 1
fi

missing=0
for image in "${images[@]}"; do
  if ! docker image inspect "${image}" >/dev/null; then
    echo "::error::Image '${image}' is not present in the local Docker daemon." >&2
    missing=1
  fi
done
if [[ "${missing}" -ne 0 ]]; then
  exit 1
fi

# JSON scan uses exit-code 0 so findings still produce a report. Crashes do not.
scan_json() {
  local json_path="$1"
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${PWD}:/work" \
    -v "${PWD}/.trivy-cache:/trivy-cache" \
    -w /work \
    "${TRIVY_IMAGE}" \
    image \
    --cache-dir /trivy-cache \
    --image-src docker \
    --scanners vuln \
    --severity "${SEVERITY}" \
    --ignore-unfixed="${IGNORE_UNFIXED}" \
    --exit-code 0 \
    --disable-telemetry \
    --skip-version-check \
    --no-progress \
    --timeout "${TRIVY_TIMEOUT}" \
    --config "${CONFIG_FILE}" \
    "${ignore_args[@]}" \
    --format json \
    --output "${json_path}" \
    "${image}"
}

# --config "" so convert does not re-read trivy.yaml and filter differently
# from the JSON scan. --scanners vuln is only for the table summary.
# Trivy 0.76 convert rejects --disable-telemetry, --skip-version-check, and
# --no-progress. The image scan still passes them; telemetry stays off there.
convert_report() {
  local format="$1"
  local output="$2"
  local code="$3"
  local json_path="$4"
  local -a output_args=()
  local -a scanner_args=()
  if [[ -n "${output}" ]]; then
    output_args=(--output "${output}")
  fi
  if [[ "${format}" == "table" ]]; then
    scanner_args=(--scanners vuln)
  fi
  docker run --rm \
    -v "${PWD}:/work" \
    -w /work \
    "${TRIVY_IMAGE}" \
    convert \
    --config "" \
    --timeout "${TRIVY_TIMEOUT}" \
    --exit-code "${code}" \
    --format "${format}" \
    "${scanner_args[@]}" \
    "${output_args[@]}" \
    "${json_path}"
}

# upload-sarif rejects multiple files that share one tool and one category.
# The id is the category when the upload step does not set one.
stamp_sarif() {
  local sarif="$1"
  local run_id="$2"
  local tmp
  tmp="$(mktemp)"
  if ! jq --arg id "${run_id}" '
    if ((.runs | type) != "array") or ((.runs | length) == 0) then
      error("SARIF has no runs")
    else
      .runs |= map(.automationDetails.id = $id)
    end
  ' "${sarif}" > "${tmp}"; then
    rm -f "${tmp}"
    return 1
  fi
  mv "${tmp}" "${sarif}"
}

failed=0
for image in "${images[@]}"; do
  safe="${image//\//_}"
  safe="${safe//:/_}"
  safe="${safe//@/_}"
  json_path="trivy-results/${safe}.json"
  sarif_path="trivy-results/${safe}.sarif"
  run_id="trivy-image-${ARTIFACT_SUFFIX}/${safe}/"
  echo "::group::${image}"

  status=0
  scan_json "${json_path}" || status=$?
  if [[ "${status}" -ne 0 || ! -s "${json_path}" ]]; then
    echo "::error::Trivy JSON scan of ${image} exited ${status}." >&2
    failed=1
    echo "::endgroup::"
    continue
  fi

  status=0
  convert_report table "" "${exit_code}" "${json_path}" || status=$?
  if [[ "${status}" -ne 0 ]]; then
    echo "::warning::Trivy table report for ${image} exited ${status}." >&2
    failed=1
  fi

  status=0
  convert_report sarif "${sarif_path}" 0 "${json_path}" || status=$?
  if [[ "${status}" -ne 0 || ! -s "${sarif_path}" ]]; then
    echo "::error::Trivy SARIF report for ${image} exited ${status}." >&2
    failed=1
    echo "::endgroup::"
    continue
  fi

  if ! stamp_sarif "${sarif_path}" "${run_id}"; then
    echo "::error::Could not set SARIF automationDetails.id for ${image}." >&2
    failed=1
  fi

  echo "::endgroup::"
done

exit "${failed}"
