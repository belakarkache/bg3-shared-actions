#!/usr/bin/env bash
set -euo pipefail

SRC="${1:?uso: $0 <arquivo.png> [potion|scroll|throw|quiver|cancel]}"
WHICH="${2:-potion}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXCONV="${TEXCONV:-texconv.exe}"
WORK_WSL="${BG3_BUILD:-build}/icon"
TILE=64

case "$WHICH" in
    potion) ATLAS="SharedActions_Icons";   ASSET="TakePotion_source.png" ;;
    scroll) ATLAS="SharedActions_Scrolls"; ASSET="UseScroll_source.png" ;;
    throw)  ATLAS="SharedActions_Throw";   ASSET="ThrowThrowables_source.png" ;;
    quiver) ATLAS="SharedActions_Quiver";  ASSET="Quiver_source.png" ;;
    cancel) ATLAS="SharedActions_Cancel";  ASSET="Cancel_source.png" ;;
    *) echo "segundo argumento: potion, scroll, throw, quiver ou cancel" >&2; exit 1 ;;
esac

[[ -f "$SRC" ]] || { echo "não achei: $SRC" >&2; exit 1; }

mkdir -p "$WORK_WSL" "$ROOT/assets"
WORK_WIN="$(wslpath -w "$WORK_WSL")"
cp "$SRC" "$WORK_WSL/$ATLAS.png"

[[ "$(readlink -f "$SRC")" == "$(readlink -f "$ROOT/assets/$ASSET")" ]] \
    || cp "$SRC" "$ROOT/assets/$ASSET"

"$TEXCONV" -w "$TILE" -h "$TILE" -m 1 -f DXT5 -dx9 -srgb -y -o "$WORK_WIN" \
    "$WORK_WIN\\$ATLAS.png" | tail -2

cp "$WORK_WSL/$ATLAS.dds" \
   "$ROOT/src/Public/SharedActions/Assets/Textures/Icons/$ATLAS.dds"

echo "OK — agora rode: ./tools/generate.sh e reempacote o mod"
