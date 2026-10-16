#!/usr/bin/env bash
# CVE findings use --exit-code 0 when SOFT_FAIL=true. A missing image or any
# other Trivy exit still fails the job. Trivy 0.76 defaults to vuln+secret;
# --scanners vuln is always passed so the secret scanner stays off.
set -euo pipefail

: "${IMAGES:?images input is required}"
: "${SOFT_FAIL:?}"
: "${SEVERITY:?}"
: "${IGNORE_UNFIXED:?}"
: "${CONFIG_FILE:?Trivy config was not resolved}"
: "${TRIVY_IMAGE:?}"
: "${TRIVY_TIMEOUT:?}"
IGNORE_FILE="${IGNORE_FILE:-}"

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

run_trivy() {
  local format="$1"
  local output="$2"
  local code="$3"
  local -a output_args=()
  if [[ -n "${output}" ]]; then
    output_args=(--output "${output}")
  fi
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
    --exit-code "${code}" \
    --disable-telemetry \
    --skip-version-check \
    --no-progress \
    --timeout "${TRIVY_TIMEOUT}" \
    --config "${CONFIG_FILE}" \
    "${ignore_args[@]}" \
    --format "${format}" \
    "${output_args[@]}" \
    "${image}"
}

failed=0
for image in "${images[@]}"; do
  safe="${image//\//_}"
  safe="${safe//:/_}"
  safe="${safe//@/_}"
  echo "::group::${image}"

  status=0
  run_trivy table "" "${exit_code}" || status=$?
  if [[ "${status}" -ne 0 ]]; then
    echo "::warning::Trivy table scan of ${image} exited ${status}." >&2
    failed=1
  fi

  status=0
  run_trivy json "trivy-results/${safe}.json" 0 || status=$?
  if [[ "${status}" -ne 0 || ! -s "trivy-results/${safe}.json" ]]; then
    echo "::error::Trivy JSON report for ${image} exited ${status}." >&2
    failed=1
  fi

  status=0
  run_trivy sarif "trivy-results/${safe}.sarif" 0 || status=$?
  if [[ "${status}" -ne 0 || ! -s "trivy-results/${safe}.sarif" ]]; then
    echo "::error::Trivy SARIF report for ${image} exited ${status}." >&2
    failed=1
  fi

  echo "::endgroup::"
done

exit "${failed}"
