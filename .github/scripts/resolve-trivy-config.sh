#!/usr/bin/env bash
# Resolve which trivy.yaml to use: explicit input, consumer root, or shared default.
set -euo pipefail

explicit="${1:-}"
shared_default="${2:-.foxglove-actions/trivy/trivy.yaml}"
consumer_root="${3:-trivy.yaml}"

if [[ -n "${explicit}" ]]; then
  if [[ ! -f "${explicit}" ]]; then
    echo "::error::config_file '${explicit}' does not exist." >&2
    exit 1
  fi
  echo "config_file=${explicit}" >> "${GITHUB_OUTPUT}"
  echo "Using explicit Trivy config: ${explicit}"
  exit 0
fi

if [[ -f "${consumer_root}" ]]; then
  # Prefer a non-empty consumer file that is more than comments/whitespace.
  if grep -Eqv '^[[:space:]]*(#|$)' "${consumer_root}"; then
    echo "config_file=${consumer_root}" >> "${GITHUB_OUTPUT}"
    echo "Using consumer Trivy config: ${consumer_root}"
    exit 0
  fi
  echo "Consumer ${consumer_root} is comments-only; falling back to shared defaults."
fi

if [[ -f "${shared_default}" ]]; then
  echo "config_file=${shared_default}" >> "${GITHUB_OUTPUT}"
  echo "Using shared Trivy config: ${shared_default}"
  exit 0
fi

echo "::error::No Trivy config file found." >&2
exit 1
