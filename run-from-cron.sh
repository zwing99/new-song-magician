#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v uv >/dev/null 2>&1 && [[ -x "/home/linuxbrew/.linuxbrew/bin/uv" ]]; then
  export PATH="/home/linuxbrew/.linuxbrew/bin:$PATH"
fi

if [[ -f "$SCRIPT_DIR/.envrc" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "$SCRIPT_DIR/.envrc"
  set +a
fi

folder_id="${1:-${PCO_REVIEW_FOLDER_FOLDER_ID:-}}"
if [[ -z "$folder_id" ]]; then
  echo "Set PCO_REVIEW_FOLDER_FOLDER_ID or pass the folder ID as the first argument." >&2
  exit 1
fi

if [[ $# -gt 0 ]]; then
  shift
fi

exec uv run python main.py review-folder "$folder_id" --no-print "$@"
