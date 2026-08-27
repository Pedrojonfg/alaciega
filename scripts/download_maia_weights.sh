#!/bin/sh
# ponytail: curl + skip-if-exists; no python wrapper
set -eu
DIR="${MAIA_WEIGHTS_DIR:-/app/weights}"
LEVELS="${MAIA_LEVELS:-1100,1300,1500,1700,1900}"
BASE="${MAIA_WEIGHTS_URL:-https://github.com/CSSLab/maia-chess/releases/download/v1.0}"
mkdir -p "$DIR"
IFS=,
for level in $LEVELS; do
  level=$(printf '%s' "$level" | tr -d ' ')
  [ -n "$level" ] || continue
  dest="$DIR/maia-${level}.pb.gz"
  [ -f "$dest" ] && continue
  tmp="$dest.part"
  curl -fsSL -o "$tmp" "$BASE/maia-${level}.pb.gz"
  mv "$tmp" "$dest"
done
