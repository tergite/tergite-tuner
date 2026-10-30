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
"""Pins each node's analysis of a recorded dataset to the QOIs it gave when this test was added.

A change that moves a value on purpose rewrites its golden with
``UPDATE_GOLDENS=1 pytest tergite_tuner/tests/test_reanalysis_goldens.py``,
and the commit says why.
"""

import json
import math
import os
from pathlib import Path

import pytest

from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.goldens import (
    RECORDED_DATASETS,
    get_analyser,
    get_state_file,
)
from tergite_tuner.tests.utils.state import loaded_state

GOLDENS_DIR = Path(get_fixture_path("goldens"))
# relative tolerance across platforms' floating point and fitting libraries
TOLERANCE = 1e-6
# fitted values the data constrains loosely, which platforms' last bits move further
LOOSE_TOLERANCES = {"Ql": 1e-3}
# choices whose deciding fit sits within its own uncertainty of the threshold, so
# platforms' fits fall either side: q08's last punchout shift is 98.5 kHz against
# the 100 kHz threshold, from a fit uncertain by 13.5 kHz
EITHER_VALUE = {"punchout": {"q08/measure:pulse_amp": (0.04525, 0.06)}}


@pytest.mark.parametrize("case", RECORDED_DATASETS)
def test_reanalysis_gives_the_golden_qois(case, session_context, tmp_path):
    golden_case = RECORDED_DATASETS[case]
    analyse = get_analyser(golden_case, tmp_path, session_context)
    with loaded_state(session_context, get_state_file(golden_case)):
        qois = analyse()

    values = _get_flat_values(qois)
    golden_path = GOLDENS_DIR / f"{case}.json"
    if os.environ.get("UPDATE_GOLDENS"):
        golden_path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n")
    golden = json.loads(golden_path.read_text())
    either = EITHER_VALUE.get(case, {})
    for key, choices in either.items():
        value = values.pop(key)
        assert any(value == pytest.approx(choice) for choice in choices), value
        golden.pop(key)
    numbers = {key for key, value in golden.items() if _is_number(value)}
    assert {k: v for k, v in values.items() if k not in numbers} == {
        k: v for k, v in golden.items() if k not in numbers
    }
    assert {k: values.get(k) for k in numbers} == {
        k: pytest.approx(
            golden[k], rel=LOOSE_TOLERANCES.get(k.split("/")[1], TOLERANCE)
        )
        for k in numbers
    }


def _get_flat_values(qois: dict) -> dict:
    """``{"q06/rxy:amp180": 0.6, "q06/is_successful": True, ...}``, as approx compares flat dicts only."""
    values = {}
    for element, qoi in sorted(qois.items()):
        values[f"{element}/is_successful"] = qoi.analysis_successful
        for name, result in qoi.analysis_result.items():
            value = result["value"]
            if hasattr(value, "tolist"):
                value = value.tolist()
            if isinstance(value, list):
                for index, item in enumerate(value):
                    values[f"{element}/{name}/{index}"] = _to_json(item)
            else:
                values[f"{element}/{name}"] = _to_json(value)
    return values


def _to_json(value):
    if hasattr(value, "item"):
        value = value.item()
    return None if isinstance(value, float) and math.isnan(value) else value


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
