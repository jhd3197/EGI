#!/usr/bin/env bash
# Run the full Android validation loop: lint, unit tests, and (if devices are
# available) instrumented tests. Exits non-zero on any failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=detect-env.sh
source "$SCRIPT_DIR/detect-env.sh"

cd "$PROJECT_DIR"

echo "==> Running lint..."
./gradlew lintDebug

echo "==> Running JVM unit tests..."
./gradlew test

echo "==> Building debug APK..."
./gradlew assembleDebug

# Run instrumented tests only if at least one authorized device is attached.
mapfile -t SERIALS < <(adb devices -l | awk '/^[0-9A-Za-z]+ +device / {print $1}')
if [[ ${#SERIALS[@]} -gt 0 ]]; then
    echo "==> Running instrumented tests on ${#SERIALS[@]} device(s)..."
    ./gradlew connectedCheck
else
    echo "==> No authorized devices attached; skipping instrumented tests."
fi

echo "==> All checks passed."
