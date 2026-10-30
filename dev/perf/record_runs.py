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
"""Measures whole runs: the dummy tune-up, the fast tests, the import, the install.

python -m dev.perf.record_runs <runs.json>
"""

import json
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

IMPORT_ROUNDS = 5


def main(output_path: str) -> None:
    tune_up_seconds, tune_up_rss_mb = measure_command(
        [
            "pytest",
            "tergite_tuner/tests/test_tune_up.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ]
    )
    suite_seconds, _ = measure_command(
        ["pytest", "tergite_tuner", "-q", "-p", "no:cacheprovider", "-m", "not slow"]
    )
    install_mb, package_count = measure_install()
    measurements = {
        "dummy_tune_up": {"seconds": tune_up_seconds, "peak_memory_mb": tune_up_rss_mb},
        "fast_test_suite": {"seconds": suite_seconds},
        "import": {"seconds": measure_import_seconds()},
        "install": {"size_mb": install_mb, "packages": package_count},
    }
    Path(output_path).write_text(
        json.dumps(measurements, indent=2, sort_keys=True) + "\n"
    )


def measure_command(command: list[str]) -> tuple[float, float]:
    """Wall time and peak resident memory of a command, run in its own process."""
    start = time.perf_counter()
    subprocess.run([sys.executable, "-m", *command], check=False, capture_output=True)
    seconds = time.perf_counter() - start
    peak_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # macOS reports bytes, Linux kilobytes
    peak_rss_mb = peak_rss / 2**20 if sys.platform == "darwin" else peak_rss / 2**10
    return seconds, peak_rss_mb


def measure_import_seconds() -> float:
    """The fastest of a few imports, as other load on the machine only ever slows one down."""
    return min(_get_import_seconds() for _ in range(IMPORT_ROUNDS))


def measure_install() -> tuple[float, int]:
    """Size and package count of a fresh environment with the package's own dependencies."""
    requirements = _run(
        ["uv", "export", "--locked", "--no-dev", "--no-hashes", "--no-emit-project"]
    )
    packages = [
        line for line in requirements.splitlines() if line and line[0].isalnum()
    ]
    with tempfile.TemporaryDirectory() as directory:
        venv = Path(directory) / "venv"
        _run(["uv", "venv", "-q", "--python", sys.executable, str(venv)])
        requirements_file = Path(directory) / "requirements.txt"
        requirements_file.write_text(requirements)
        _run(
            [
                "uv",
                "pip",
                "install",
                "-q",
                "--python",
                str(venv / "bin" / "python"),
                "-r",
                str(requirements_file),
            ]
        )
        size = sum(path.stat().st_size for path in venv.rglob("*") if path.is_file())
    return size / 2**20, len(packages)


def _get_import_seconds() -> float:
    """Cumulative import time of tergite_tuner, from ``-X importtime``."""
    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "import tergite_tuner"],
        capture_output=True,
        text=True,
        check=True,
    )
    line = next(
        row for row in result.stderr.splitlines() if row.endswith("| tergite_tuner")
    )
    return int(line.split("|")[1]) / 1e6


def _run(command: list[str]) -> str:
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout


if __name__ == "__main__":
    main(sys.argv[1])
