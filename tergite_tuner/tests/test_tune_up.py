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

from tergite_tuner.lib.nodes import DEFAULT_NODE_SPECS
from tergite_tuner.tests.utils.runs import DEFAULT_NODES, run_dummy_node
from tergite_tuner.utils.types.node_enum import NodeEnum

# each fails on a defect REFACTOR.md lists; strict, so a fix fails the test until removed
_KNOWN_FAILURES = {
    NodeEnum.QUBIT_01_SPECTROSCOPY: "five 6 us spectroscopy amplitudes overflow the waveform memory",
    NodeEnum.ALL_XY: "AllXY cannot run (step 9.7)",
    NodeEnum.PURITY_BENCHMARKING: "purity benchmarking cannot run (step 9.7)",
}
_DEFAULT_NODES = [
    pytest.param(
        node,
        id=node.value,
        marks=(
            [pytest.mark.xfail(reason=_KNOWN_FAILURES[node], strict=True)]
            if node in _KNOWN_FAILURES
            else []
        ),
    )
    for node in DEFAULT_NODES
]


@pytest.mark.slow
@pytest.mark.parametrize("node", _DEFAULT_NODES)
def test_every_default_node_runs_in_dummy_mode(
    node, session_context, tmp_path, monkeypatch
):
    # the dummy cluster assembles in the working directory, which workers would share
    monkeypatch.chdir(tmp_path)
    run_dummy_node(node, session_context, tmp_path)

    # analyses of random IQ points may fail; reaching them without raising is the check
    # a node may save under another node's name (step 9.8)
    node_name = DEFAULT_NODE_SPECS[node].name.value
    assert list(tmp_path.glob(f"*-run/dataset_{node_name}.hdf5"))


def test_unkept_data_files_delete_only_the_runs_folder(
    session_context, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "out"
    earlier_file = data_dir / "earlier" / "dataset.hdf5"
    earlier_file.parent.mkdir(parents=True)
    earlier_file.touch()

    run_dummy_node(
        NodeEnum.RESONATOR_SPECTROSCOPY,
        session_context,
        data_dir,
        keep_data_files=False,
    )

    assert sorted(data_dir.rglob("*")) == [earlier_file.parent, earlier_file]
