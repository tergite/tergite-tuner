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


from types import SimpleNamespace

import pytest

from tergite_tuner.lib import run
from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.lib.nodes.readout.resonator_spectroscopy.node import (
    RESONATOR_SPECTROSCOPY_SPECS,
)
from tergite_tuner.lib.spec import Fit
from tergite_tuner.storage.fs.dataset import load_dataset
from tergite_tuner.tests.utils.goldens import (
    RECORDED_DATASETS,
    STANDARD_REDIS,
    copy_dataset,
    get_dataset_path,
    get_redis_file,
)
from tergite_tuner.tests.utils.state import loaded_state
from tergite_tuner.utils.types.node_enum import NodeEnum

RESONATOR = DEFAULT_NODE_SPECS[NodeEnum.RESONATOR_SPECTROSCOPY]


@pytest.mark.parametrize("state_node", list(RESONATOR_SPECTROSCOPY_SPECS))
def test_plot_elements_saves_the_preview_and_the_full_plot(
    state_node, session_context, tmp_path
):
    spec = DEFAULT_NODE_SPECS[state_node]
    case = RECORDED_DATASETS["standard_run_resonator_spectroscopy"]
    name = RESONATOR.name.value
    copy_dataset(get_dataset_path(case.dataset), tmp_path / f"dataset_{name}.hdf5")
    s21s = run.get_element_s21s(load_dataset(name, tmp_path))
    with loaded_state(session_context, get_redis_file(case)):
        run.plot_elements(
            spec,
            s21s,
            run.get_fits(spec, s21s, session_context),
            tmp_path,
            session_context,
        )

    assert (tmp_path / f"{spec.name.value}_preview.png").exists()
    assert (tmp_path / f"{spec.name.value}.png").exists()


def test_a_node_is_in_spec_only_where_it_is_calibrated(session_context):
    qubit, other = session_context.qubits[:2]
    session_context.state.load({"cs": {qubit: {RESONATOR.name.value: "calibrated"}}})

    assert run.is_in_spec(RESONATOR.name.value, [qubit], session_context)
    assert not run.is_in_spec(RESONATOR.name.value, [other], session_context)


def test_failed_fits_mark_their_element_not_calibrated(session_context):
    qubit, other = session_context.qubits[:2]
    session_context.state.load({"cs": {other: {RESONATOR.name.value: "calibrated"}}})
    fits = {name: Fit(1.0, 0.1) for name in RESONATOR.qois}

    run.store_fits(RESONATOR, {qubit: fits, other: None}, session_context)

    state = session_context.state
    assert state.read("cs", qubit, RESONATOR.name.value) == "calibrated"
    assert state.read("cs", other, RESONATOR.name.value) == "not_calibrated"
    for field in RESONATOR.qois.values():
        assert state.read("transmons", qubit, field) == 1.0
        assert state.read("transmons", qubit, f"{field}_error") == 0.1


class _Spi:
    def __init__(self):
        self.currents = None

    def set_dac_current(self, currents: dict):
        self.currents = currents


@pytest.mark.parametrize("is_recalibration", [True, False])
def test_parking_currents_are_set_unless_recalibrating(
    session_context, is_recalibration
):
    session = session_context.model_copy(update={"is_recalibration": is_recalibration})
    hardware = SimpleNamespace(spi=_Spi())
    with loaded_state(session, STANDARD_REDIS):
        run.set_parking_currents(hardware, session)

    expected = None if is_recalibration else {"q00_q01": 0.00095}
    assert hardware.spi.currents == expected
