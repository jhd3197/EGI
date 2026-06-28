#!/usr/bin/env bash
# Regenerate visual-regression baselines for the PWA smoke test (plan-19 Phase 5).
#
# Runs the smoke test (which captures fresh screenshots per device + journey) and
# copies the results into screenshots/baseline/<serial>/<journey>.png. Run this
# after an INTENTIONAL UI change so the next `EGI_VISUAL=1` run compares against
# the new look.
#
# Baselines are per-device (resolution-matched) and are intentionally NOT committed
# to git (see plan-19 notes / .gitignore) — they are a local artifact.
#
# Usage:
#   ./scripts/update-baselines.sh                # all connected devices
#   ./scripts/update-baselines.sh <serial> ...   # specific devices
#   ./scripts/update-baselines.sh --no-build ... # reuse the installed APK
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTS="$PROJECT_DIR/test-results"
BASELINE="$PROJECT_DIR/screenshots/baseline"
JOURNEYS=(guest alias report)

echo "==> Capturing a fresh run to use as baselines..."
# Don't gate baseline capture on a prior baseline; run functional smoke (visual off).
EGI_VISUAL=0 bash "$SCRIPT_DIR/pwa-smoke-test.sh" "$@"

echo "==> Copying screenshots into $BASELINE ..."
shopt -s nullglob
for devdir in "$RESULTS"/*/; do
    serial="$(basename "$devdir")"
    [[ "$serial" == "mesh" ]] && continue
    mkdir -p "$BASELINE/$serial"
    for j in "${JOURNEYS[@]}"; do
        if [[ -f "$devdir/$j.png" ]]; then
            cp "$devdir/$j.png" "$BASELINE/$serial/$j.png"
            echo "  $serial/$j.png"
        fi
    done
done

echo "==> Done. Baselines updated. Future runs: EGI_VISUAL=1 ./scripts/pwa-smoke-test.sh"
