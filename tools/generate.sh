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

SPELLS_EXPORT="${SE_MOD_CONFIG:-}/SharedActions/spells.json"
if [[ -f "$SPELLS_EXPORT" ]]; then
    mkdir -p data
    cp "$SPELLS_EXPORT" data/spells.json
fi

python3 tools/generate_stats.py
python3 tests/test_generate.py
