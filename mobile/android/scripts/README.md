# EGI Android Automation Scripts

These scripts make it possible for an AI agent (or a human) to build, install,
configure, and validate the EGI Android app on real devices without memorizing
Gradle/ADB commands.

## Quick start

```bash
cd mobile/android
source scripts/detect-env.sh
./scripts/install-and-configure.sh
./scripts/run-tests.sh
```

## Scripts

### `detect-env.sh`

Sources the Android Studio bundled JDK and the SDK from `local.properties`.
Run this first in any fresh terminal:

```bash
source scripts/detect-env.sh
```

### `devices.py`

Lists connected ADB devices and whether EGI is installed.

```bash
./scripts/devices.py
./scripts/devices.py --json
```

### `install-and-configure.sh`

Builds the debug APK and installs it on every authorized device, then grants
all runtime permissions needed for mesh/SMS testing and takes a launch
screenshot.

```bash
./scripts/install-and-configure.sh
```

### `run-tests.sh`

Runs lint, JVM unit tests, builds the APK, and runs instrumented tests if a
device is attached.

```bash
./scripts/run-tests.sh
```

### `mesh-smoke-test.py`

Two-device smoke test. Requires two authorized phones and the debug APK.
It installs, clears data, launches the app, enables mesh, and polls logcat for
mesh events.

```bash
./scripts/mesh-smoke-test.py
```

## What an AI agent can do with these

- Run `run-tests.sh` on every PR and report regressions.
- Auto-fix lint errors and update Room schemas.
- Use `devices.py` to pick test devices and warn about unauthorized ones.
- Run `install-and-configure.sh` to prepare phones for field demos.
- Run `mesh-smoke-test.py` to prove two phones exchange records.
- Capture screenshots, battery deltas, and logcat dumps for debugging.
