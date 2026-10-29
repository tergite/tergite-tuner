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
"""A ``measure`` fixture that records each benchmark's median time and peak memory.

Our own, not pytest-benchmark: its latest release (5.3.0) reads a private pytest attribute
that pytest 9.2 removed.
"""

import json
import statistics
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

ROUNDS = 3
_RESULTS: dict[str, dict[str, float]] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--perf-json", help="the file to write the measurements to")


@pytest.fixture
def measure(request: pytest.FixtureRequest) -> Callable[[Callable[[], Any]], None]:
    def record(action: Callable[[], Any]) -> None:
        _RESULTS[request.node.name] = {
            "seconds": _get_median_seconds(action),
            "peak_memory_mb": _get_peak_memory_mb(action),
        }

    return record


def pytest_sessionfinish(session: pytest.Session) -> None:
    path = session.config.getoption("--perf-json")
    if path and _RESULTS:
        Path(path).write_text(json.dumps(_RESULTS, indent=2, sort_keys=True) + "\n")


def _get_median_seconds(action: Callable[[], Any]) -> float:
    durations = []
    for _ in range(ROUNDS):
        start = time.perf_counter()
        action()
        durations.append(time.perf_counter() - start)
    return statistics.median(durations)


def _get_peak_memory_mb(action: Callable[[], Any]) -> float:
    tracemalloc.start()
    try:
        action()
        return tracemalloc.get_traced_memory()[1] / 2**20
    finally:
        tracemalloc.stop()
