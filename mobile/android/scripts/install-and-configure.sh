#!/usr/bin/env bash
# Build the EGI debug APK, install it on every authorized device, and grant
# runtime permissions needed for mesh/SMS testing.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source env detection (works even if user forgot JAVA_HOME)
# shellcheck source=detect-env.sh
source "$SCRIPT_DIR/detect-env.sh"

cd "$PROJECT_DIR"

APK="app/build/outputs/apk/debug/app-debug.apk"
SCREENSHOT_DIR="$PROJECT_DIR/screenshots"
mkdir -p "$SCREENSHOT_DIR"

echo "==> Building debug APK..."
./gradlew assembleDebug

echo "==> Installing and configuring devices..."
mapfile -t SERIALS < <(adb devices -l | awk '/^[0-9A-Za-z]+ +device / {print $1}')

if [[ ${#SERIALS[@]} -eq 0 ]]; then
    echo "ERROR: No authorized devices found." >&2
    exit 1
fi

for serial in "${SERIALS[@]}"; do
    echo "--- Device $serial ---"

    echo "  Installing APK..."
    adb -s "$serial" install -r "$APK"

    echo "  Granting permissions..."
    adb -s "$serial" shell pm grant com.egi.app android.permission.BLUETOOTH_CONNECT || true
    adb -s "$serial" shell pm grant com.egi.app android.permission.BLUETOOTH_SCAN || true
    adb -s "$serial" shell pm grant com.egi.app android.permission.BLUETOOTH_ADVERTISE || true
    adb -s "$serial" shell pm grant com.egi.app android.permission.ACCESS_FINE_LOCATION || true
    adb -s "$serial" shell pm grant com.egi.app android.permission.ACCESS_COARSE_LOCATION || true
    adb -s "$serial" shell pm grant com.egi.app android.permission.RECEIVE_SMS || true
    adb -s "$serial" shell pm grant com.egi.app android.permission.POST_NOTIFICATIONS || true

    echo "  Whitelisting from Doze..."
    adb -s "$serial" shell dumpsys deviceidle whitelist +com.egi.app || true

    echo "  Launching app..."
    adb -s "$serial" shell monkey -p com.egi.app -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
    sleep 2

    screenshot="$SCREENSHOT_DIR/$serial-launch.png"
    adb -s "$serial" exec-out screencap -p > "$screenshot" || true
    echo "  Screenshot: $screenshot"
done

echo "==> Done. ${#SERIALS[@]} device(s) ready."
