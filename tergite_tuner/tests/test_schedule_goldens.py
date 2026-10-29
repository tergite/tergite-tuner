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
"""Pins every default node's compiled program: sequencer programs, waveforms, settings, acquisitions.

A change that alters a program on purpose rewrites its digest with
``UPDATE_GOLDENS=1 pytest tergite_tuner/tests/test_schedule_goldens.py``, and the commit says why.
"""

import dataclasses
import hashlib
import json
import os
from enum import Enum
from pathlib import Path

import numpy as np
import pytest

from tergite_tuner.lib.nodes import DEFAULT_NODE_NAME_CLS_MAP
from tergite_tuner.tests.utils.fixtures import get_fixture_path
from tergite_tuner.tests.utils.goldens import get_first_samplespace
from tergite_tuner.tests.utils.redis import loaded_redis
from tergite_tuner.utils.types.extended_transmon import ExtendedTransmon

GOLDEN_FILE = Path(get_fixture_path("goldens")) / "schedules.json"
REDIS_VALUES = get_fixture_path("redis", "standard_redis_mock.json")
# below the last bits in which platforms' maths libraries differ
SIGNIFICANT_DIGITS = 9
# purity benchmarking cannot be built (step 9.7)
NODE_NAMES = [
    name for name in DEFAULT_NODE_NAME_CLS_MAP if name != "purity_benchmarking"
]


@pytest.mark.parametrize("node_name", NODE_NAMES)
def test_compiled_program_matches_its_golden(
    node_name, redis_connection, session_context
):
    with loaded_redis(redis_connection, REDIS_VALUES):
        ExtendedTransmon.close_all()
        node = DEFAULT_NODE_NAME_CLS_MAP[node_name](
            all_qubits=["q00", "q01"], couplers=["q00_q01"], session=session_context
        )
        compiled = node.precompile(get_first_samplespace(node))

    digest = _get_digest(compiled.compiled_instructions)
    goldens = json.loads(GOLDEN_FILE.read_text()) if GOLDEN_FILE.exists() else {}
    if os.environ.get("UPDATE_GOLDENS"):
        goldens[node_name] = digest
        GOLDEN_FILE.write_text(json.dumps(goldens, indent=2, sort_keys=True) + "\n")
    assert digest == goldens.get(node_name)


def _get_digest(compiled_instructions: dict) -> str:
    canonical = json.dumps(_to_canonical(compiled_instructions), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _to_canonical(value):
    if dataclasses.is_dataclass(value):
        return _to_canonical(dataclasses.asdict(value))
    if isinstance(value, dict) and value and all(_is_hash_key(key) for key in value):
        # waveform names are Python hashes, seeded per process; programs use their index
        items = [_to_canonical(item) for item in value.values()]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, dict):
        return {str(key): _to_canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_to_canonical(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (float, np.floating)):
        return float(f"{value:.{SIGNIFICANT_DIGITS}g}")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return repr(value)


def _is_hash_key(key) -> bool:
    return isinstance(key, str) and key.lstrip("-").isdigit()
