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

import pytest

from tergite_tuner.exc import MissingCalibrationStatusError
from tergite_tuner.lib import run
from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.storage.fs.dataset import load_dataset
from tergite_tuner.tests.utils.goldens import (
    RECORDED_DATASETS,
    copy_dataset,
    get_dataset_path,
    get_redis_file,
)
from tergite_tuner.tests.utils.redis import loaded_redis
from tergite_tuner.utils.types.node_enum import NodeEnum

RESONATOR = DEFAULT_NODE_SPECS[NodeEnum.RESONATOR_SPECTROSCOPY]


@pytest.mark.parametrize("state_node", list(DEFAULT_NODE_SPECS))
def test_plot_elements_saves_the_preview_and_the_full_plot(
    state_node, redis_connection, session_context, tmp_path
):
    spec = DEFAULT_NODE_SPECS[state_node]
    case = RECORDED_DATASETS["standard_run_resonator_spectroscopy"]
    name = RESONATOR.name.value
    copy_dataset(get_dataset_path(case.dataset), tmp_path / f"dataset_{name}.hdf5")
    s21s = run.get_element_s21s(load_dataset(name, tmp_path))
    with loaded_redis(redis_connection, get_redis_file(case)):
        run.plot_elements(
            spec, s21s, run.get_fits(spec, s21s), tmp_path, session_context
        )

    assert (tmp_path / f"{spec.name.value}_preview.png").exists()
    assert (tmp_path / f"{spec.name.value}.png").exists()


def test_mark_not_calibrated_keeps_existing_statuses(redis_connection, session_context):
    qubit, other = session_context.qubits[:2]
    redis_connection.hset(f"cs:{qubit}", RESONATOR.name.value, "calibrated")

    run.mark_not_calibrated(RESONATOR, session_context)

    assert run.is_in_spec(RESONATOR.name.value, [qubit], session_context)
    assert not run.is_in_spec(RESONATOR.name.value, [other], session_context)


def test_a_missing_status_raises(session_context):
    with pytest.raises(MissingCalibrationStatusError):
        run.is_in_spec(RESONATOR.name.value, session_context.qubits, session_context)
