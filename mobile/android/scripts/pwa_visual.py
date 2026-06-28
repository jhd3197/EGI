#!/usr/bin/env python3
"""Perceptual screenshot diff for the PWA smoke tests (plan-19 Phase 5).

Compares a freshly captured screenshot against a stored per-device baseline and
returns the fraction of pixels that differ beyond a tolerance. Used to catch
unintended visual regressions of the embedded PWA (e.g. the landing page changing
without an updated baseline).

Baselines live under (gitignored) mobile/android/screenshots/baseline/<serial>/
<journey>.png — keyed by device serial so resolution always matches. The actual
images are intentionally NOT committed (see plan-19 notes); update-baselines.sh
regenerates them locally from a known-good run.

Diff metric: per-pixel max channel delta > PIXEL_TOLERANCE counts as "changed";
the score is changed_pixels / total_pixels (0.0 identical … 1.0 fully different).
A small writable diff image highlighting changed pixels can be saved alongside.

Requires Pillow + numpy (already used by the server). CLI:
    python pwa_visual.py <baseline.png> <candidate.png> [diff_out.png]
"""
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    np = None
    Image = None

PIXEL_TOLERANCE = 24  # per-channel 0..255 delta below which a pixel is "same"


def available():
    return np is not None and Image is not None


def _load(path, size=None):
    img = Image.open(path).convert("RGB")
    if size is not None and img.size != size:
        img = img.resize(size)
    return img


def diff_ratio(baseline_path, candidate_path, diff_out=None):
    """Return (ratio, detail). ratio is fraction of changed pixels (0..1)."""
    if not available():
        return None, "pillow/numpy unavailable"
    if not os.path.exists(baseline_path):
        return None, "no baseline"
    if not os.path.exists(candidate_path):
        return None, "no candidate"
    base = _load(baseline_path)
    cand = _load(candidate_path, size=base.size)
    a = np.asarray(base, dtype=np.int16)
    b = np.asarray(cand, dtype=np.int16)
    delta = np.abs(a - b).max(axis=2)  # max channel delta per pixel
    changed = delta > PIXEL_TOLERANCE
    ratio = float(changed.mean())
    if diff_out:
        # Red overlay where pixels changed, for human inspection.
        out = np.asarray(cand, dtype=np.uint8).copy()
        out[changed] = [255, 0, 0]
        Image.fromarray(out).save(diff_out)
    return ratio, "ok (%.3f%% changed)" % (ratio * 100)


def main(argv):
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    diff_out = argv[3] if len(argv) > 3 else None
    ratio, detail = diff_ratio(argv[1], argv[2], diff_out)
    print("%s ratio=%s" % (detail, ratio))
    return 0 if (ratio is not None and ratio < 0.05) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
