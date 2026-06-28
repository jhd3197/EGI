#!/usr/bin/env bash
# EGI PWA WebView smoke test — build + install the debug APK, then drive the
# embedded PWA on every connected device (Journeys A/B/C) over the Chrome DevTools
# Protocol. Exits non-zero if any journey fails, so CI can gate on it.
#
# Usage:
#   ./scripts/pwa-smoke-test.sh                 # build, install, test all devices
#   ./scripts/pwa-smoke-test.sh --no-build      # skip build/install (reuse what's on device)
#   ./scripts/pwa-smoke-test.sh <serial> ...    # restrict to specific devices
#
# Artifacts: mobile/android/test-results/<serial>/{guest,alias,report}.{png,json},
#            console.log, result.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

NO_BUILD=0
SERIALS=()
for arg in "$@"; do
    case "$arg" in
        --no-build) NO_BUILD=1 ;;
        *) SERIALS+=("$arg") ;;
    esac
done

if [[ "$NO_BUILD" -eq 0 ]]; then
    echo "==> Building + installing debug APK on all devices..."
    "$SCRIPT_DIR/install-and-configure.sh"
else
    echo "==> Skipping build/install (--no-build)."
fi

# Pick a Python interpreter (python or python3).
PY="python"
command -v python >/dev/null 2>&1 || PY="python3"

# websocket-client is required by the CDP driver.
if ! "$PY" -c "import websocket" >/dev/null 2>&1; then
    echo "==> Installing websocket-client (CDP dependency)..."
    "$PY" -m pip install --quiet websocket-client
fi

echo "==> Running PWA journeys over CDP..."
cd "$PROJECT_DIR"
"$PY" "$SCRIPT_DIR/pwa_smoke_test.py" "${SERIALS[@]}"
