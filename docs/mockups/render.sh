#!/usr/bin/env bash
# Renders each docs/mockups/*.html to docs/images/<name>.png with headless Chrome.
# The capture size comes from each file's <meta name="render-size" content="WxH">.
#
#   docs/mockups/render.sh                 # every mockup
#   docs/mockups/render.sh assessments     # one mockup, by file name
#
# Set CHROME to the Chrome/Chromium binary if it is not in the default macOS spot.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
out="$here/../images"
chrome="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
mkdir -p "$out"

if [ $# -gt 0 ]; then
  files=()
  for name in "$@"; do files+=("$here/$name.html"); done
else
  files=("$here"/*.html)
fi

for file in "${files[@]}"; do
  name="$(basename "$file" .html)"
  size="$(sed -n 's/.*name="render-size" content="\([0-9]*x[0-9]*\)".*/\1/p' "$file" | head -1)"
  if [ -z "$size" ]; then
    echo "skip $name: no render-size meta" >&2
    continue
  fi
  "$chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=2 \
    --window-size="${size/x/,}" --virtual-time-budget=10000 \
    --screenshot="$out/$name.png" "file://$file" 2>/dev/null
  echo "rendered $name ($size @2x) -> docs/images/$name.png"
done
