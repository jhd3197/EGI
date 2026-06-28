#!/usr/bin/env bash
# EGI Android environment detector.
# Sources standard Android Studio / SDK paths and exports JAVA_HOME, ANDROID_SDK_ROOT, PATH.
# Usage: source mobile/android/scripts/detect-env.sh

set -euo pipefail

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "This script is meant to be sourced, not executed."
    echo "Usage: source $(basename "$0")"
    exit 1
fi

# --- JDK detection -----------------------------------------------------------
to_unix_path() {
    local p="$1"
    p="${p//\\//}"
    if [[ "$p" =~ ^([A-Za-z]):/(.*)$ ]]; then
        p="/${BASH_REMATCH[1],,}/${BASH_REMATCH[2]}"
    fi
    echo "$p"
}

find_jdk() {
    # 1. Existing JAVA_HOME
    if [[ -n "${JAVA_HOME:-}" && -x "$(to_unix_path "$JAVA_HOME")/bin/java" ]]; then
        to_unix_path "$JAVA_HOME"
        return
    fi

    # 2. Android Studio bundled JBR (JetBrains Runtime)
    local jbr="/c/Program Files/Android/Android Studio/jbr"
    if [[ -x "$jbr/bin/java" ]]; then
        echo "$jbr"
        return
    fi

    # 3. JetBrains Toolbox / other Android Studio installs
    local candidates=(
        "$HOME/AppData/Local/JetBrains/Toolbox/apps/AndroidStudio/ch-0/*/jbr"
        "$HOME/AppData/Local/Programs/Android Studio/jbr"
        "/c/Program Files/Android/Android Studio 2/jbr"
    )
    for c in "${candidates[@]}"; do
        for d in $c; do
            if [[ -x "$d/bin/java" ]]; then
                echo "$d"
                return
            fi
        done
    done

    # 4. Any java on PATH
    if command -v java &>/dev/null; then
        to_unix_path "$(dirname "$(dirname "$(command -v java)")")"
        return
    fi

    echo ""
}

JDK="$(find_jdk)"
if [[ -z "$JDK" ]]; then
    echo "ERROR: Could not find a JDK. Install Android Studio or set JAVA_HOME." >&2
    return 1
fi
export JAVA_HOME="$JDK"
export PATH="$JAVA_HOME/bin:$PATH"

# --- Android SDK detection ---------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_PROPERTIES="$PROJECT_DIR/local.properties"

if [[ -f "$LOCAL_PROPERTIES" ]] && grep -q '^sdk.dir=' "$LOCAL_PROPERTIES"; then
    SDK_DIR="$(grep '^sdk.dir=' "$LOCAL_PROPERTIES" | cut -d= -f2 | tr -d '\r')"
    # Convert Windows path to Unix for Git Bash (C:\foo -> /c/foo)
    SDK_DIR="${SDK_DIR//\\//}"
    if [[ "$SDK_DIR" =~ ^([A-Za-z]):/(.*)$ ]]; then
        SDK_DIR="/${BASH_REMATCH[1],,}/${BASH_REMATCH[2]}"
    fi
else
    SDK_DIR="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/AppData/Local/Android/Sdk}}"
fi

if [[ ! -d "$SDK_DIR" ]]; then
    echo "ERROR: Android SDK not found at $SDK_DIR" >&2
    return 1
fi

export ANDROID_SDK_ROOT="$SDK_DIR"
export ANDROID_HOME="$SDK_DIR"
export PATH="$SDK_DIR/platform-tools:$PATH"

# --- Verify ------------------------------------------------------------------
java -version >/dev/null 2>&1 || {
    echo "ERROR: java is not executable in $JAVA_HOME/bin" >&2
    return 1
}
adb version >/dev/null 2>&1 || {
    echo "ERROR: adb not found in $SDK_DIR/platform-tools" >&2
    return 1
}

echo "EGI Android env ready"
echo "  JAVA_HOME=$JAVA_HOME"
echo "  ANDROID_SDK_ROOT=$ANDROID_SDK_ROOT"
echo "  adb=$(command -v adb)"
