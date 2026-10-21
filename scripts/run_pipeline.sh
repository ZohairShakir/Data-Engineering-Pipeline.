#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example and set a local database password." >&2
  exit 2
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv. Run 'make setup' first." >&2
  exit 2
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

.venv/bin/python -m pipeline run "$@"
.venv/bin/python -m pipeline analytics
