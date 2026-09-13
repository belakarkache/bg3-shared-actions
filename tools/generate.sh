#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

WORKSPACE_ENV="../../bin/env.sh"
if [[ -z "${BG3_DATA:-}" && -f "$WORKSPACE_ENV" ]]; then
    source "$WORKSPACE_ENV"
    export BG3_DATA="$GAMEDATA" BG3_BUILD="$BUILD_DIR" BG3_GAME_DATA="$BG3_DATA_WIN" \
           DIVINE="$DIVINE" TEXCONV="$TEXCONV"
fi

python3 tools/collect.py
python3 tools/generate_stats.py
python3 tests/test_generate.py
