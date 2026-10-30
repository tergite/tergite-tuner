# This code is part of Tergite
#
# (C) Copyright Chalmers Next Labs 2025
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.


from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.lib.run import get_dataset, get_dummy_dataset, get_sweeps
from tergite_tuner.tests.utils.fixtures import (
    get_fixture_path,
)
from tergite_tuner.tests.utils.goldens import get_dataset_builder
from tergite_tuner.tests.utils.state import loaded_state
from tergite_tuner.utils.types.node_enum import NodeEnum

redis_mock = get_fixture_path("redis", "standard_redis_mock.json")


def test_get_dataset_labels_each_qubits_sweep(session_context):
    spec = DEFAULT_NODE_SPECS[NodeEnum.RESONATOR_SPECTROSCOPY]
    session = session_context.model_copy(update={"user_samplespace": {}})
    sweeps = get_sweeps(spec, session)

    dataset = get_dataset(
        get_dummy_dataset(spec, sweeps, session), sweeps, session.qubits
    )

    assert dataset.attrs["elements"] == sorted(session.qubits)
    assert len(dataset.data_vars) == len(session.qubits)
    assert dataset["yq00"].attrs["qubit"] == "q00"
    assert dataset["yq00"].shape == sweeps["ro_frequencies"]["q00"].shape
    assert dataset.coords["ro_frequenciesq00"].attrs["element_type"] == "qubit"


def test_get_dataset_gives_a_coupler_node_a_variable_per_qubit(session_context):
    with loaded_state(session_context, redis_mock):
        dataset = get_dataset_builder("coupler_anticrossing", session_context)()

    assert dataset.attrs["elements"] == ["q00_q01"]
    assert set(dataset.data_vars) == {"yq00", "yq01"}
    assert dataset["yq00"].attrs["element"] == "q00_q01"
    assert dataset.coords["spec_frequenciesq00"].attrs["element_type"] == "qubit"


def test_get_dataset_puts_loops_last(session_context):
    spec = DEFAULT_NODE_SPECS[NodeEnum.RANDOMIZED_BENCHMARKING]
    session = session_context.model_copy(update={"user_samplespace": {}})
    sweeps = get_sweeps(spec, session)

    dataset = get_dataset(
        get_dummy_dataset(spec, sweeps, session), sweeps, session.qubits, spec.loops
    )

    cliffords = len(sweeps["number_of_cliffords"]["q00"])
    assert dataset["yq00"].shape == (cliffords, spec.loops)
    assert dataset.coords["number_of_cliffordsq00"].attrs["element_type"] == "qubit"
    assert dataset.coords["loops"].size == spec.loops


def test_get_dataset_labels_a_couplers_sweeps_by_coupler(session_context):
    with loaded_state(session_context, redis_mock):
        dataset = get_dataset_builder("cz_parametrization", session_context)()

    assert dataset["yq00"].attrs["element"] == "q00_q01"
    assert dataset["yq00"].shape == (25, 28, 128)
    coords = dataset.coords
    assert coords["cz_pulse_amplitudesq00_q01"].attrs["element_type"] == "coupler"
