#!/usr/bin/env bash
# Resolve which checkov.yml to use: explicit input, consumer root, or shared default.
set -euo pipefail

explicit="${1:-}"
shared_default="${2:-.foxglove-actions/checkov/checkov.yml}"
consumer_root="${3:-checkov.yml}"

if [[ -n "${explicit}" && -f "${explicit}" ]]; then
  echo "config_file=${explicit}" >> "${GITHUB_OUTPUT}"
  echo "Using explicit Checkov config: ${explicit}"
  exit 0
fi

if [[ -f "${consumer_root}" ]]; then
  # Prefer a non-empty consumer file that is more than comments/whitespace.
  if grep -Eqv '^[[:space:]]*(#|$)' "${consumer_root}"; then
    echo "config_file=${consumer_root}" >> "${GITHUB_OUTPUT}"
    echo "Using consumer Checkov config: ${consumer_root}"
    exit 0
  fi
  echo "Consumer ${consumer_root} is comments-only; falling back to shared defaults."
fi

if [[ -f "${shared_default}" ]]; then
  echo "config_file=${shared_default}" >> "${GITHUB_OUTPUT}"
  echo "Using shared Checkov config: ${shared_default}"
  exit 0
fi

echo "config_file=" >> "${GITHUB_OUTPUT}"
echo "No Checkov config file found; relying on action inputs only."
