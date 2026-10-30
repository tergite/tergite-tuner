# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs AB 2026
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
"""Fails when a recording is worse than the baseline by more than the threshold.

    python -m dev.perf.compare dev/perf/baselines/<machine> <recording dir>

Every measure is lower-is-better: seconds, megabytes, packages.
"""

import json
import sys
from pathlib import Path

# two recordings on one busy MacBook differed by up to 11% (import), 9% (memory), 8% (tests)
THRESHOLD = 0.15
# below these, differences are noise rather than a regression
NOISE_FLOORS = {
    "seconds": 0.05,
    "peak_memory_mb": 1.0,
    "size_mb": 1.0,
    "packages": 0,
    "store_round_trips": 0,
}
RECORDINGS = ("nodes.json", "runs.json")


def main(baseline_dir: str, recording_dir: str) -> int:
    baseline = _read_measures(Path(baseline_dir))
    recording = _read_measures(Path(recording_dir))
    regressions = [
        f"{name}: {baseline[name]:.3f} -> {recording[name]:.3f}"
        for name in sorted(baseline.keys() & recording.keys())
        if is_regression(name, baseline[name], recording[name])
    ]
    missing = sorted(baseline.keys() - recording.keys())
    for title, lines in (
        ("Worse than the baseline", regressions),
        ("Not recorded", missing),
    ):
        if lines:
            print(f"{title}:")
            print("\n".join(f"  {line}" for line in lines))
    return 1 if regressions or missing else 0


def is_regression(name: str, baseline: float, recording: float) -> bool:
    noise_floor = NOISE_FLOORS[name.rsplit("/", 1)[1]]
    return recording - baseline > max(baseline * THRESHOLD, noise_floor)


def _read_measures(directory: Path) -> dict[str, float]:
    """``{"nodes.json/test_compile[punchout]/seconds": 0.8, ...}``"""
    measures = {}
    for recording in RECORDINGS:
        for subject, values in json.loads((directory / recording).read_text()).items():
            for measure, value in values.items():
                measures[f"{recording}/{subject}/{measure}"] = value
    return measures


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
