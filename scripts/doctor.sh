#!/usr/bin/env bash
# Run the env + tool checks. Useful before opening an issue to a peer agent.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run rag-demo doctor
